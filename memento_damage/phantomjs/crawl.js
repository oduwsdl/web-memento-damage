var system = require('system');
var fs = require('fs');
var page = require('webpage').create();
console.error = function () {
    require("system").stderr.write(Array.prototype.join.call(arguments, ' ') + '\n');
};

page.settings.webSecurityEnabled = false;
phantom.injectJs('md5.js');
phantom.injectJs('underscore.js');
phantom.injectJs('mimetype.js');

var networkResources = {};
var Log = {'DEBUG': 10, 'INFO': 20};
var starttime = Date.now();

// If number of arguments after crawl.js is not 2, show message and exit phantomjs
if (system.args.length < 3) {
    console.error('Usage: phantomjs crawl.js <URI> <output_dir> [redirect] [viewport_w x viewport_h] [log_level]');
    phantom.exit(1);
}

// Else, continue opening URI
else {
    // use 1st param after crawl.js as URL input and 2nd param as output
    url = system.args[1];
    hashedUrl = md5(url);
    outputDir = system.args[2];
    followRedirect = false;
    viewportSize = [1024, 768];
    logLevel = Log.DEBUG;

    if(system.args.length >= 4) {
        followRedirect = (system.args[3].toLowerCase() == 'true' || system.args[3] == '1');
    }

    if(system.args.length >= 5) {
        strViewportSize = system.args[4].toLowerCase().split("x");
        if(strViewportSize.length == 2) {
            viewportSize = [parseInt(strViewportSize[0]), parseInt(strViewportSize[1])];
        }
    }

    if(system.args.length >= 6) {
        logLevel = parseInt(system.args[5]);
    }

    // Set timeout on fetching resources to 30 seconds (can be changed)
    page.settings.resourceTimeout = 30000;
    page.onResourceTimeout = function(e) {
        console.error('Resource ' + e.url + ' timeout. ' + e.errorCode + ' ' + e.errorString);
    };

    // Use browser size 1024x768 (to be used on screenshot)
    page.viewportSize = { width: viewportSize[0], height: viewportSize[1] };

    // Set error handler
    page.onError = function(msg, trace) {
        var msgStack = ['PHANTOM ERROR: ' + msg];
        if (trace && trace.length) {
            msgStack.push('TRACE:');
            trace.forEach(function(t) {
                msgStack.push(' -> ' + (t.file || t.sourceURL) + ': ' + t.line + (t.function ? ' (in function ' + t.function +')' : ''));
            });
        }
        console.error(msgStack.join('\n'));
    };

    // Set console to debug
    page.onConsoleMessage = function(msg, lineNum, sourceId) {
        if(logLevel <= Log.DEBUG) console.log('CONSOLE: ' + msg + ' (from line #' + lineNum + ' in "' + sourceId + '")');
    };

    page.onResourceError = function(res) {
        page.errorMessage = res.errorString;
        console.error(res.errorString);
    };

    pageStatusCode = null;
    isAborted = false;
    abortMessage= '';

    // Request will be execute before resource received
    page.onResourceRequested = function(res, req) {
        if(isAborted) req.abort();

        if(!followRedirect && (pageStatusCode === 301 || pageStatusCode === 302)) {
            isAborted = true;
            if(pageStatusCode === 301) {
                abortMessage = 'Page is moved permanently (Status code 301)';
            } else if(pageStatusCode === 302) {
                abortMessage = 'Page is found, but redirected (Status code 302)';
            }
            req.abort();
        }

        else if(pageStatusCode == 404) {
            isAborted = true;
            abortMessage = 'Page not found (Status code 404)';
            req.abort();
        }
    };

    // Resource is similiar with all listed in developer tools -> network tab -> refresh
    page.onResourceReceived = function (res) {
        resUrl = res.url;
        resStatus = res.status;

        if (resUrl == url) {
            pageStatusCode = resStatus;
            if(logLevel <= Log.INFO && res.stage === 'start') console.log('Receiving resource(s)');
        }

        if((!followRedirect && (pageStatusCode === 301 || pageStatusCode === 302)) || (pageStatusCode == 404)) {
            return;
        }

        // Handle base64 image (have 'data' scheme), set status code to 200
        if(resUrl.indexOf('data') == 0) {
            resStatus = 200;
        }

        if(res.stage === 'start') {
            if(logLevel <= Log.DEBUG) console.log('Resource ' + resUrl + ' (' + resStatus + ') is being received');
        } else if(res.stage === 'end') {
            if(logLevel <= Log.DEBUG) console.log('Resource ' + resUrl + ' (' + resStatus + ') is received');
        }

        // Save all network resources to variable
        // res are sometimes duplicated, so only pushed if array hasnt contains this value
        // use underscore.js to check whether value has been contained in networkResources key
        headers = {};
        res.headers.forEach(function(header) {
            headers[header['name']] = header['value'];
        });

        var resource = {
            'url' : resUrl,
            'status_code' : resStatus,
            'content_type' : resStatus > 399 ? mimeType.lookup(resUrl) : res.contentType,
            'headers' : headers,
        };

        var networkResourcesKeys = Object.keys(networkResources);
        if(! _.contains(networkResourcesKeys, resUrl)) {
            // Sometimes url received in quoted (encoded) format, so decode it
            resUrl = decodeURIComponent(resUrl);
            networkResources[resUrl] = resource;
        }
    };

    page.onLoadFinished = function (status) {
        if(isAborted) {
            processPage(url, outputDir);

            //? what's the difference between console.log vs console.error?
            //? where can I find this 'crawl-result' print out?
            //? I run this and see the output on terminal, just wanna see whether it printed 'crawl-result'
                //? or not. Apparently it's not.

            console.error(JSON.stringify({'crawl-result' : {
              'uri' : url,
              'status_code' : pageStatusCode,
              'error' : true,
              'message' : abortMessage,
            }}));

            phantom.exit(pageStatusCode);
        }

        else if (status !== 'success') {
            processPage(url, outputDir);
            console.error(JSON.stringify({'crawl-result' : {
              'uri' : url,
              'status_code' : pageStatusCode,
              'error' : true,
              'message' : 'Error in loading url. ' + page.errorMessage + '.',
            }}));

            phantom.exit(1);
        }

        else {
            if(logLevel <= Log.INFO) console.log('Page is loaded');

            // After page is opened, process page.
            // Use setTimeout to delay process
            // Timeout in ms, means 200 ms
            window.setTimeout(function () {
                if (page.injectJs('jquery-3.1.0.min.js') && page.injectJs('underscore.js') && page.injectJs('isInViewport.min.js')) {
                    // Calculate bgcolor
                    var bgcolor = getBackgroundColor();
                    // If bgcolor == 000000 -> change it to white
                    if(bgcolor == '000000') {
                        page.evaluate(function() {
                            document.body.style.backgroundColor = '#ffffff';
                        });
                    }

                    processPage(url, outputDir);
                    // Show bgcolor
                    if(logLevel <= Log.ERROR) console.log(JSON.stringify({'background_color' : getBackgroundColor()}));

                    // Set finished time
                    var finishtime = Date.now();

                    // Show message that crawl finished, and calculate executing time
                    if(logLevel <= Log.INFO) console.log('Crawl finished in ' + (finishtime - starttime) + ' miliseconds');
                    if(logLevel <= Log.DEBUG) console.log(JSON.stringify({'crawl-result' : {
                      'uri' : url,
                      'status_code' : pageStatusCode,
                      'error' : false,
                      'message' : 'Crawl finished in ' + (finishtime - starttime) + ' miliseconds',
                    }}));

                    phantom.exit();
                }
            }, 10000);
        }
    };

    // Kill crawl.js, after 5 minutes not responding
    window.setTimeout(function () {
        phantom.exit(1);
    }, 5 * 60 * 1000);

    // Open URI
    if(logLevel <= Log.INFO) console.log('Start crawling URI ' + url);
    page.open(url);

}

function processPage(url, outputDir) {
    processNetworkResources(url, outputDir);
    processHtml(url, outputDir);
    processImages(url, outputDir);
    processMultimedias(url, outputDir);
    processCsses(url, outputDir);
    processJavascripts(url, outputDir);
    processScreenshots(url, outputDir);
    processText(url, outputDir);
}

function processNetworkResources(url, outputDir) {
    resourceFile = outputDir + '/network.log';

    // Save all resources
    // networkResources are sometimes duplicated
    // use filter as described in http://stackoverflow.com/questions/1960473/unique-values-in-an-array
    networkResourcesValues = []
    var networkResourcesKeys = Object.keys(networkResources);
    for(r=0; r<networkResourcesKeys.length; r++) {
        var value = networkResources[networkResourcesKeys[r]];
        networkResourcesValues.push(JSON.stringify(value));
    }

    fs.write(resourceFile, unescape(encodeURIComponent(networkResourcesValues.join('\n'))), "w");
    if(logLevel <= Log.DEBUG) console.log('Saving network resources --> creating ' + resourceFile);
}

function processHtml(url, outputDir) {
    htmlFile = outputDir + '/source.html';

    // Save html using fs.write
    // DOM selection or modification always be done inside page.evaluate
    var html = page.evaluate(function() {
        return document.body.parentElement.outerHTML;
    });
    fs.write(htmlFile, html, "w");

    if(logLevel <= Log.INFO) console.log('Saving HTML source --> creating ' + htmlFile);
}

function processImagesInFrame() {
    // Get images using document.images
    // document.images also can be execute in browser console
    var images = page.evaluate(function () {
        var allImages = {};
        var documentImages = document.images;

        for(var i=0; i<documentImages.length; i++) {
            var docImage = documentImages[i];

            // Make defaults value
            allImages[docImage['src']] = {};
            allImages[docImage['src']]['url'] = docImage['src'];
            allImages[docImage['src']]['rectangles'] = [];
        }

        for(var i=0; i<documentImages.length; i++) {
            var docImage = documentImages[i];

            // Calculate vieport size
            allImages[docImage['src']]['viewport_size'] = [
                docImage.ownerDocument.body.clientWidth,
                docImage.ownerDocument.body.clientHeight
            ];

            // get the height and width of each element
            var width = $(docImage).outerWidth(false);         // source: http://stackoverflow.com/questions/9276633/get-absolute-height-and-width
            var height = $(docImage).outerHeight(false);

            // calculate absolute top-left position of the object --> find the coordinate
            var top = $(docImage).offset().top;
            var left = $(docImage).offset().left;

            rectangle = {
                'width' : width,
                'height' : height,
                'top' : top,
                'left' : left,
            }

            allImages[docImage['src']]['rectangles'].push(rectangle);
        }

        return allImages;
    }) || {};

    return images;
}

function processImages(url, outputDir) {
    var images = processImagesInFrame();
    for(var f=0; f<page.framesCount; f++) {
        if(!_.includes(page.framesName[f], 'fb_') && !_.includes(page.framesName[f], 'twitter-')) {
            page.switchToFrame(page.framesName[f]);
            var imagesFrame = processImagesInFrame();
            // textLog = textLog.concat(textLogFrame);
            _.extend(images, imagesFrame);
        }
    }
    page.switchToMainFrame();
        console.error('ini adalah images: ' + JSON.stringify(images));
    // Check images url == resource url, append position if same
    var networkImages = {};
    var docImageUrls = Object.keys(images);
    for(url in networkResources) {
        if(networkResources[url]['content_type']) {
            if(networkResources[url]['content_type'].indexOf('image/') == 0) {
                networkImages[url] = networkResources[url];
                docImageUrls.forEach(function(diUrl, idx) {
                    //console.error('ini adalah diUrl and url: ' + diUrl + " - " + url);
                    if(url.indexOf(diUrl) >= 0) {
                        networkImages[url] = _.extend(networkImages[url], images[diUrl]);
                    }
                });

                if(! ('viewport_size' in networkImages[url])) {
                    networkImages[url]['viewport_size'] = viewportSize;
                }

                networkImages[url]['rectangles'] = networkImages[url]['rectangles'] || [];

                if(! ('url' in networkImages[url]))    {
                    networkImages[url]['url'] = url;
                }
            }
        }
    }

    // Save all resource images
    var values = [];
    var keys = Object.keys(networkImages);
    for(r=0; r<keys.length; r++) {
        var value = networkImages[keys[r]];
        values.push(JSON.stringify(value));
    }

    resourceImageFile = outputDir + '/image.log';
//    console.log("values = " + values + "\n");
//    console.log("values.join = " + (values.join('\n')) + "\n");
//    console.log("value = " + values[0] + "\n");
//    console.log("value encodeURIComponent = " + encodeURIComponent(values[0]));
//    console.log("value encode unescape = " + unescape(encodeURIComponent(values[0])));
    fs.write(resourceImageFile, unescape(encodeURIComponent(values.join('\n'))), "w");
    //fs.write(resourceImageFile, (values.join('\n')), "w");
    if(logLevel <= Log.INFO) console.log('Processing images --> creating ' + resourceImageFile);
}

function processMultimediasInFrame() {
    // Get videos using document.getElementsByTagName("video")
    // document.getElementsByTagName("video") also can be execute in browser console
    var videos = page.evaluate(function () {
        var documentVideos =  document.getElementsByTagName("video");
        var allVideos = {};

        for(var i=0; i<documentVideos.length; i++) {
            var docVideo = documentVideos[i];
//            allVideos[docVideo['currentSrc']] = {};
//            allVideos[docVideo['currentSrc']]['url'] = url;
//            allVideos[docVideo['currentSrc']]['rectangles'] = [];

            var pat = /^https?:\/\//i;
            if(pat.test(docVideo['src']))    {
                allVideos[docVideo['src']] = {};
                allVideos[docVideo['src']]['url'] = docVideo['src'];
                allVideos[docVideo['src']]['rectangles'] = [];
            }
            else    {
                allVideos[docVideo['currentSrc']] = {};
                allVideos[docVideo['currentSrc']]['url'] = docVideo['currentSrc'];
                allVideos[docVideo['currentSrc']]['rectangles'] = [];
            }
        }

        for(var i=0; i<documentVideos.length; i++) {
            var docVideo = documentVideos[i];

            // Calculate vieport size
            allVideos[docVideo['currentSrc']]['viewport_size'] = [
                docVideo.ownerDocument.body.clientWidth,
                docVideo.ownerDocument.body.clientHeight
            ];

            // Computed styles
            var cs = window.getComputedStyle(docVideo);
            var width = parseFloat(cs.width.replace('px', '')) || docVideo.clientWidth;
            var height = parseFloat(cs.height.replace('px', '')) || docVideo.clientHeight;

            // Calculate top left position
//            var obj = docVideo;
//            var left = 0, top = 0;
//            do {
//                left += obj.offsetLeft;
//                top += obj.offsetTop;
//            } while (obj = obj.offsetParent);


            var left = 0, top = 0;
            do {
                left += docVideo.offsetLeft;                    // alternative: elem.getBoundingClientRect()  --> has been tested.
                top += docVideo.offsetTop;
            } while (docVideo = docVideo.offsetParent);


            rectangle = {
                'width' : width,
                'height' : height,
                'top' : top,
                'left' : left,
            };

            allVideos[docVideo['currentSrc']]['rectangles'].push(rectangle);
        }

        return allVideos;
    }) || {};

    return videos;
}

function processMultimedias(url, outputDir) {
    var videos = processMultimediasInFrame();
    for(var f=0; f<page.framesCount; f++) {
        if(!_.includes(page.framesName[f], 'fb_') && !_.includes(page.framesName[f], 'twitter-')) {
            page.switchToFrame(page.framesName[f]);
            var videosFrame = processMultimediasInFrame();
            // textLog = textLog.concat(textLogFrame);
            _.extend(videos, videosFrame);
        }
    }
    page.switchToMainFrame();

    // Check images url == resource url, append position if same
    var networkVideos = {};
    var docVideoUrls = Object.keys(videos);
    for(url in networkResources) {
        if(networkResources[url]['content_type']) {
            if(networkResources[url]['content_type'].indexOf('video/') == 0) {
                networkVideos[url] = networkResources[url];
                docVideoUrls.forEach(function(dvUrl, idx) {
                    if(networkVideos[url]['url'].indexOf(dvUrl) >= 0)    {       // if docVideoUrls contains dvUrl
                        networkVideos[url] = _.extend(networkVideos[url], videos[dvUrl]);
                    }
                });

                if(! ('viewport_size' in networkVideos[url])) {
                    networkVideos[url]['viewport_size'] = viewportSize;
                }

                if(! ('rectangles' in networkVideos[url])) {
                    networkVideos[url]['rectangles'] = [];
                }

                networkVideos[url]['url'] = url;
            }
        }
    }

    // Save all resource images
    var networkVideosValues = []
    var networkVideosKeys = Object.keys(networkVideos);
    for(r=0; r<networkVideosKeys.length; r++) {
        var value = networkVideos[networkVideosKeys[r]];
        networkVideosValues.push(JSON.stringify(value));
    }

    resourceVideoFile = outputDir + '/video.log';
    fs.write(resourceVideoFile, unescape(encodeURIComponent(networkVideosValues.join('\n'))), "w");
    if(logLevel <= Log.INFO) console.log('Processing videos --> creating ' + resourceVideoFile);
}

function processCssesInFrame() {
    var csses = page.evaluate(function () {
        // $.noConflict();
        function getSelectorTextRecursive(rule, rules_tag) {
            // Reference for type https://developer.mozilla.org/en-US/docs/Web/API/CSSRule#Type_constants
            if(rule.type == 1) { // CSSStyleRule
                var tag = rule.selectorText;
                rules_tag.push(tag);
            } else if(rule.type == 4) { // CSSMediaRule
                var subRules = rule.cssRules;
                for(var sr=0; sr<subRules.length; sr++) {
                    rules_tag = getSelectorTextRecursive(subRules[sr], rules_tag);
                }
            }

            return rules_tag;
        }

        function serialize(docCss) {
            var rules_tag = [];
            // For each stylesheet, get its rules
            var rules = docCss.cssRules || docCss.rules || [];
            // For each rule, get selectorText
            for(var r=0; r<rules.length; r++) {
                var rule = rules[r];
                rules_tag = getSelectorTextRecursive(rule, rules_tag);
            }
            // Calculate importance
            importance = 0;
            for(var r=0; r<rules_tag.length; r++) {
                var tag = rules_tag[r];
                try {
                    importance += $(tag).length;
                } catch(e) {}
            }
            // Create json containing url and rules
            var jsonCss = {
                'url' : docCss['href'] || '[INTERNAL]',
                'rules_tag' : rules_tag || [],
                'hash' : docCss.ownerNode.outerHTML,
                'importance': importance,
            };

            return jsonCss;
        }

        var jsonCsses = [];
        var docCsses = document.styleSheets || [];
        for(t=0; t<docCsses.length; t++) jsonCsses.push(serialize(docCsses[t]));

        return jsonCsses;
    }) || {};

    return csses;
}

function processCsses(url, outputDir) {
    var csses = processCssesInFrame();
    for(var f=0; f<page.framesCount; f++) {
        if(!_.includes(page.framesName[f], 'fb_') && !_.includes(page.framesName[f], 'twitter-')) {
            page.switchToFrame(page.framesName[f]);
            var cssesFrame = processCssesInFrame();
            // textLog = textLog.concat(textLogFrame);
            _.extend(csses, cssesFrame);
        }
    }
    page.switchToMainFrame();

    // Check css url == resource url, append position if same
    var networkCsses = []
    var networkResourcesKeys = Object.keys(networkResources);
    for(var i=0; i<csses.length; i++) {
        var css = csses[i];

        if('hash' in css) css['hash'] = md5(css['hash']);
        if(! ('rules_tag' in css)) css['rules_tag'] = [];

        idx = _.indexOf(networkResourcesKeys, css['url']);
        if(idx >= 0) {
            var networkCss = networkResources[networkResourcesKeys[idx]];
            css = _.extend(css, networkCss);
        }

        networkCsses.push(css);
    }

    // Save all resource csses
    // var resourceCssFile = path.join(resourceDir, resourceBasename + '.css.log');
    networkCssValues = []
    for(r=0; r<networkCsses.length; r++) {
        networkCssValues.push(JSON.stringify(networkCsses[r]));
    }

    resourceCssFile = outputDir + '/css.log';
    fs.write(resourceCssFile, unescape(encodeURIComponent(networkCssValues.join('\n'))), "wb");
    if(logLevel <= Log.INFO) console.log('Processing stylesheets --> creating ' + resourceCssFile);
}

function processJavascriptsInFrame() {
    var jses = page.evaluate(function () {
        function serialize(docJs) {
            // Create json containing url and rules
            var jsonJs = {
                'url' : docJs['src'] || '[INTERNAL]',
            };

            return jsonJs;
        }

        var allJses = [];
        var tmpJses = document.scripts || [];
        for(t=0; t<tmpJses.length; t++) allJses.push(serialize(tmpJses[t]));
        return allJses;
    }) || {};

    return jses;
}

function processJavascripts(url, outputDir) {
    var jses = processJavascriptsInFrame();
    for(var f=0; f<page.framesCount; f++) {
        if(!_.includes(page.framesName[f], 'fb') && !_.includes(page.framesName[f], 'twitter-')) {
            page.switchToFrame(page.framesName[f]);
            var jsesFrame = processJavascriptsInFrame();
            // textLog = textLog.concat(textLogFrame);
            _.extend(jses, jsesFrame);
        }
    }
    page.switchToMainFrame();

    // Check css url == resource url, append position if same
    var networkJses = []
    var networkResourcesKeys = Object.keys(networkResources);
    for(var i=0; i<jses.length; i++) {
        var js = jses[i];

        idx = _.indexOf(networkResourcesKeys, js['url']);
        if(idx >= 0) {
            var networkJs = networkResources[networkResourcesKeys[idx]];
            js = _.extend(js, networkJs);
        }

        networkJses.push(js);
    }

    // Save all resource csses
    // var resourceCssFile = path.join(resourceDir, resourceBasename + '.css.log');
    networkJsValues = []
    for(r=0; r<networkJses.length; r++) {
        networkJsValues.push(JSON.stringify(networkJses[r]));
    }

    resourceJsFile = outputDir + '/js.log';
    fs.write(resourceJsFile, unescape(encodeURIComponent(networkJsValues.join('\n'))), "wb");
    if(logLevel <= Log.INFO) console.log('Processing javascript --> creating ' + resourceJsFile);
}

function processScreenshots(url, outputDir) {
    screenshotFile = outputDir + '/screenshot.png';

    // Save screenshot
    page.render(screenshotFile);
    if(logLevel <= Log.INFO) console.log('Processing screenshot --> creating ' + screenshotFile);
}

function processTextInFrame() {
    var textLog = page.evaluate(function() {
        // $.noConflict();

        var allElements = {};
        var textLog = {};
        $('body').find('*').each(function(idx, el) {
            var originalCs = getComputedStyle(this);
            var originalText = $(this).text().replace(/\n\s+\n/g,'\n\n').replace(/ \s+ /g,' ');
            var outerHTML = this.outerHTML
            var outerTag = this.cloneNode(false).outerHTML

            // get the height and width of each element
            var oW = $(this).outerWidth(false);         // source: http://stackoverflow.com/questions/9276633/get-absolute-height-and-width
            var oH = $(this).outerHeight(false);

            // calculate absolute top-left position of the object --> find the coordinate
            var curtop = $(this).offset().top;
            var curleft = $(this).offset().left;

            allElements[idx] = this;

            var visible = false;
            if ($(this).is(':visible') || $(this).is(':not(:hidden)') ||
                originalCs['display'] == '' || originalCs['display'] != 'none' ||
                originalCs['visibility'] == '' || originalCs['visibility'] == 'visible') {
                visible = true;
            }

            var inViewport = false;
            if ($(this).is(':in-viewport')) {
                inViewport = true;
            }

            if(this.childElementCount == 0) {
                var text = $(this).text();
            } else {
                var text = "";
            }

            textLog[idx] = {
                'id': idx,
                'html': outerHTML,
                'tag': outerTag,
                'original-text': originalText.trim(),
                'visible': visible,
                'in-viewport': inViewport,
                'text': text.trim(),
                'top': curtop,
                'left': curleft,
                'width': parseFloat(oW),
                'height': parseFloat(oH),
            };
        });

        var elIdxs = Object.keys(allElements).reverse();
        for (var i = 0; i < elIdxs.length; i++) {
            var idx = elIdxs[i];

            // If element has children, try remove all children and see what text is left
            if (allElements[idx].childElementCount > 0) {
                for(var c=0; c<allElements[idx].childElementCount; c++) {
                    $(allElements[idx].children[c]).remove();
                }

                try {
                    var cs = window.getComputedStyle(allElements[idx]);
                    textLog[idx]['text'] = $(this).text().trim();
                    textLog[idx]['width'] = parseFloat(cs.width.replace('px', '')) || 0;
                    textLog[idx]['height'] = parseFloat(cs.height.replace('px', '')) || 0;
                } catch(ex) {}
            }

            // Calculate coverage by simulating fixed position
            if (textLog[idx]['text'].length > 0) {
                // Make element not wrapped
                $(allElements[idx]).css('position', 'fixed').css('top', '0px')
                    .css('left', '0px').css('width', 'auto').css('height', 'auto')
                    .css('white-space', 'nowrap');

                // Calculate coverage
                var cs = window.getComputedStyle(allElements[idx]);
                var w = parseFloat(cs.width.replace('px', '')) || 0;
                var h = parseFloat(cs.height.replace('px', '')) || 0;
                textLog[idx]['coverage'] = w * h;

                // Put back original element
                $(allElements[idx]).replaceWith(textLog[idx]['html']);
            }
        }

        var arrTextLogs = [];
        var elIdxs = Object.keys(textLog);
        for (var i = 0; i < elIdxs.length; i++) {
            idx = elIdxs[i];
            if(textLog[idx]['text'].length > 0) {
                arrTextLogs.push(JSON.stringify(textLog[idx]));
            }
        }

        return arrTextLogs;
    }) || [];

    return textLog;
}

function processText(url, outputDir) {
    var textLog = processTextInFrame();
    for(var f=0; f<page.framesCount; f++) {
        if(!_.includes(page.framesName[f], 'fb_') && !_.includes(page.framesName[f], 'twitter-')) {
            page.switchToFrame(page.framesName[f]);
            var textLogFrame = processTextInFrame();
            textLog = textLog.concat(textLogFrame);
        }
    }
    page.switchToMainFrame();

    resourceTextFile = outputDir + '/text.log';
    fs.write(resourceTextFile, unescape(encodeURIComponent(textLog.join('\n'))), "wb");
    if (logLevel <= Log.INFO) console.log('Processing text --> creating ' + resourceTextFile);
}

function getBackgroundColor() {
    return page.evaluate(function() {
        function rgb2hex(orig){
            var rgb = orig.replace(/\s/g,'').match(/^rgba?\((\d+),(\d+),(\d+)/i);
            return (rgb && rgb.length === 4) ? "" +
            ("0" + parseInt(rgb[1],10).toString(16)).slice(-2) +
            ("0" + parseInt(rgb[2],10).toString(16)).slice(-2) +
            ("0" + parseInt(rgb[3],10).toString(16)).slice(-2) : orig;
        }

        var bgColor = window.getComputedStyle(document.body)['backgroundColor'];
        return rgb2hex(bgColor) || 'FFFFFF';
    })
}
