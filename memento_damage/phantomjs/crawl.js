var system = require('system');
var fs = require('fs');
var page = require('webpage').create();
console.error = function () {
    require("system").stderr.write(Array.prototype.join.call(arguments, ' ') + '\n');
};

page.settings.webSecurityEnabled = false;
phantom.injectJs('md5.js')
phantom.injectJs('underscore.js')
phantom.injectJs('mimetype.js')

var networkResources = {}
var Log = {'DEBUG': 10, 'INFO': 20}
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
    followRedirect = false
    viewportSize = [1024, 768]
    logLevel = Log.DEBUG

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
        logLevel = parseInt(system.args[5])
    }

    // Set timeout on fetching resources to 30 seconds (can be changed)
    page.settings.resourceTimeout = 300000;
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
        page.errorMessage = res.errorString
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

        if (resUrl == url) {
            pageStatusCode = res.status;
            if(logLevel <= Log.INFO && res.stage === 'start') console.log('Receiving resource(s)');
        }

        if((!followRedirect && (pageStatusCode === 301 || pageStatusCode === 302)) || (pageStatusCode == 404)) {
            return;
        }

        if(res.stage === 'start') {
            if(logLevel <= Log.DEBUG) console.log('Resource ' + resUrl + ' (' + res.status + ') is being received');
        } else if(res.stage === 'end') {
            if(logLevel <= Log.DEBUG) console.log('Resource ' + resUrl + ' (' + res.status + ') is received');
        }

        // Save all network resources to variable
        // res are sometimes duplicated, so only pushed if array hasnt contains this value
        // use underscore.js to check whether value has been contained in networkResources key
        headers = {}
        res.headers.forEach(function(header) {
            headers[header['name']] = header['value'];
        });

        var resource = {
            'url' : resUrl,
            'status_code' : res.status,
            'content_type' : res.status > 399 ? mimeType.lookup(resUrl) : res.contentType,
            'headers' : headers,
        }

        var networkResourcesKeys = Object.keys(networkResources);
        if(! _.contains(networkResourcesKeys, resUrl)) {
            networkResources[resUrl] = resource;
        }
    };

    page.onLoadFinished = function (status) {
        if(isAborted) {
            processPage(url, outputDir);

            console.error(JSON.stringify({'crawl-result' : {
              'uri' : url,
              'status_code' : pageStatusCode,
              'error' : true,
              'message' : abortMessage
            }}));

            phantom.exit(pageStatusCode);
        }

        else if (status !== 'success') {
            processPage(url, outputDir);

            console.error(JSON.stringify({'crawl-result' : {
              'uri' : url,
              'status_code' : pageStatusCode,
              'error' : true,
              'message' : 'Error in loading url. ' + page.errorMessage + '.'
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
                    var finishtime = Date.now()

                    // Show message that crawl finished, and calculate executing time
                    if(logLevel <= Log.INFO) console.log('Crawl finished in ' + (finishtime - starttime) + ' miliseconds');
                    if(logLevel <= Log.DEBUG) console.log(JSON.stringify({'crawl-result' : {
                      'uri' : url,
                      'status_code' : pageStatusCode,
                      'error' : false,
                      'message' : 'Crawl finished in ' + (finishtime - starttime) + ' miliseconds'
                    }}));

                    phantom.exit();
                }
            }, 5000);
        }
    }

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

    fs.write(resourceFile, networkResourcesValues.join('\n'), "w");
    if(logLevel <= Log.DEBUG) console.log('Saving network resources --> creating ' + resourceFile)
}

function processHtml(url, outputDir) {
    htmlFile = outputDir + '/source.html';

    // Save html using fs.write
    // DOM selection or modification always be done inside page.evaluate
    var html = page.evaluate(function() {
        return document.body.parentElement.outerHTML;
    });
    fs.write(htmlFile, html, "w");

    if(logLevel <= Log.INFO) console.log('Saving HTML source --> creating ' + htmlFile)
}

function processImages(url, outputDir) {
    resourceImageFile = outputDir + '/image.log';

    // Get images using document.images
    // document.images also can be execute in browser console
    var images = page.evaluate(function () {
        var allImages = {};
        var documentImages = [];

        var images = document.images || [];
        for(var i=0; i<images.length; i++) documentImages.push(images[i]);

        try {
            var frames = window.frames;
            for(var f=0; f<frames.length; f++) {
                var tmpDocument = frames[f].document;
                if(tmpDocument == undefined) tmpDocument = frames[f];

                images = tmpDocument.images || [];
                for(var i=0; i<images.length; i++) documentImages.push(images[i]);
            }
        } catch(e) {}

        for(var i=0; i<documentImages.length; i++) {
            var docImage = documentImages[i];
            allImages[docImage['currentSrc']] = {};
            allImages[docImage['currentSrc']]['rectangles'] = [];
        }

        for(var i=0; i<documentImages.length; i++) {
            var docImage = documentImages[i];

            // Calculate vieport size
            allImages[docImage['currentSrc']]['viewport_size'] = [
                docImage.ownerDocument.body.clientWidth,
                docImage.ownerDocument.body.clientHeight
            ];

            // Calculate top left position
            var obj = docImage;
            var curleft = 0, curtop = 0;
            if (obj.offsetParent) {
                do {
                    curleft += obj.offsetLeft;
                    curtop += obj.offsetTop;
                } while (obj = obj.offsetParent);
            }

            rectangle = {
                'width' : docImage['width'],
                'height' : docImage['height'],
                'top' : curtop,
                'left' : curleft,
            }

            allImages[docImage['currentSrc']]['rectangles'].push(rectangle);
        }

        return allImages;
    });

    // Check images url == resource url, append position if same
    var networkImages = {};
    var docImageUrls = Object.keys(images);
    for(url in networkResources) {
        if(networkResources[url]['content_type']) {
            if(networkResources[url]['content_type'].indexOf('image/') == 0) {
                networkImages[url] = networkResources[url];
                docImageUrls.forEach(function(diUrl, idx) {
                    if(url.indexOf(diUrl) >= 0) {
                        networkImages[url] = _.extend(networkImages[url], images[diUrl]);
                    }
                });

                if(! ('viewport_size' in networkImages[url])) {
                    networkImages[url]['viewport_size'] = viewportSize;
                }

                if(! ('rectangles' in networkImages[url])) {
                    networkImages[url]['rectangles'] = []
                }

                networkImages[url]['url'] = url;
            }
        }
    }

    // Save all resource images
    var networkImagesValues = []
    var networkImagesKeys = Object.keys(networkImages);
    for(r=0; r<networkImagesKeys.length; r++) {
        var value = networkImages[networkImagesKeys[r]];
        networkImagesValues.push(JSON.stringify(value));
    }

    fs.write(resourceImageFile, unescape(encodeURIComponent(networkImagesValues.join('\n'))), "w");
    if(logLevel <= Log.INFO) console.log('Processing images --> creating ' + resourceImageFile)
}

function processMultimedias(url, outputDir) {
    resourceVideoFile = outputDir + '/video.log';

    // Get videos using document.getElementsByTagName("video")
    // document.getElementsByTagName("video") also can be execute in browser console
    var videos = page.evaluate(function () {
        var documentVideos =  document.getElementsByTagName("video");
        var allVideos = {};

        for(var i=0; i<documentVideos.length; i++) {
            var docVideo = documentVideos[i];
            allVideos[docVideo['currentSrc']] = {};
            allVideos[docVideo['currentSrc']]['rectangles'] = []
        }

        for(var i=0; i<documentVideos.length; i++) {
            var docVideo = documentVideos[i];

            // Calculate vieport size
            allVideos[docVideo['currentSrc']]['viewport_size'] = [
                docVideo.ownerDocument.body.clientWidth,
                docVideo.ownerDocument.body.clientHeight
            ];

            // Calculate top left position
            var obj = docVideo;
            var curleft = 0, curtop = 0;
            if (obj.offsetParent) {
                do {
                    curleft += obj.offsetLeft;
                    curtop += obj.offsetTop;
                } while (obj = obj.offsetParent);
            }

            rectangle = {
                'width' : docVideo['clientWidth'],
                'height' : docVideo['clientHeight'],
                'top' : curtop,
                'left' : curleft,
            }

            allVideos[docVideo['currentSrc']]['rectangles'].push(rectangle);
        }

        return allVideos;
    });

    // Check images url == resource url, append position if same
    var networkVideos = {};
    var docVideoUrls = Object.keys(videos);
    for(url in networkResources) {
        if(networkResources[url]['content_type']) {
            if(networkResources[url]['content_type'].indexOf('video/') == 0) {
                networkVideos[url] = networkResources[url];
                docVideoUrls.forEach(function(dvUrl, idx) {
                    if(url.indexOf(dvUrl) >= 0) {
                        networkVideos[url] = _.extend(networkVideos[url], videos[dvUrl]);
                    }
                });

                if(! ('viewport_size' in networkImages[url])) {
                    networkImages[url]['viewport_size'] = viewportSize;
                }

                if(! ('rectangles' in networkVideos[url])) {
                    networkVideos[url]['rectangles'] = []
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

    fs.write(resourceVideoFile, unescape(encodeURIComponent(networkVideosValues.join('\n'))), "w");
    if(logLevel <= Log.INFO) console.log('Processing videos --> creating ' + resourceVideoFile);
}

function processCsses(url, resourceBasename) {
    resourceCssFile = outputDir + '/css.log';

    var csses = page.evaluate(function () {
        function serialize(docCss, frameId) {
            // For each stylesheet, get its rules
            var rules = docCss.cssRules || [];
            // For each rule, get selectorText
            var rules_tag = []
            for(var r=0; r<rules.length; r++) {
                var rule = rules[r].selectorText;
                rules_tag.push(rule);
            }

            // Create json containing url and rules
            var jsonCss = {
                'url' : docCss['href'] || '[INTERNAL]',
                'rules_tag' : rules_tag || [],
                'hash' : docCss.ownerNode.outerHTML,
                'frame' : frameId,
            };

            return jsonCss;
        }

        var allCsses = [];

        var tmpCsses = document.styleSheets || [];
        for(t=0; t<tmpCsses.length; t++) allCsses.push(serialize(tmpCsses[t], -1));

        var tmpFrames = window.frames;
        for(f=0; f<tmpFrames.length; f++) {
            var tmpDocument = tmpFrames[f].document;
            if(tmpDocument == undefined) tmpDocument = tmpFrames[f];

            tmpCsses = tmpDocument.styleSheets || [];
            for(t=0; t<tmpCsses.length; t++) allCsses.push(serialize(tmpCsses[t], f));
        }

        return allCsses;
    });

    // Check css url == resource url, append position if same
    var networkCsses = []
    var networkResourcesKeys = Object.keys(networkResources);
    for(var i=0; i<csses.length; i++) {
        var css = csses[i];

        if('hash' in css) css['hash'] = md5(css['hash']);

        idx = _.indexOf(networkResourcesKeys, css['url']);
        if(idx >= 0) {
            var networkCss = networkResources[networkResourcesKeys[idx]];
            css = _.extend(css, networkCss);
        }

        var importance = 0;
        if('rules_tag' in css) {
            for(var r=0; r<css['rules_tag'].length; r++) {
                var rule = css['rules_tag'][r];
                importance += calculateImportance(rule);
            }
        } else {
            css['rules_tag'] = []
        }

        css['importance'] = importance;
        networkCsses.push(css);
    }

    // Save all resource csses
    // var resourceCssFile = path.join(resourceDir, resourceBasename + '.css.log');
    networkCssValues = []
    for(r=0; r<networkCsses.length; r++) {
        networkCssValues.push(JSON.stringify(networkCsses[r]));
    }

    fs.write(resourceCssFile, unescape(encodeURIComponent(networkCssValues.join('\n'))), "wb");
    if(logLevel <= Log.INFO) console.log('Processing stylesheets --> creating ' + resourceCssFile);
}

function processScreenshots(url, outputDir) {
    screenshotFile = outputDir + '/screenshot.png';

    // Save screenshot
    page.render(screenshotFile);
    if(logLevel <= Log.INFO) console.log('Processing screenshot --> creating ' + screenshotFile);
}

function processText(url, outputDir) {
    resourceTextFile = outputDir + '/text.log';

    var textLog = page.evaluate(function() {
        var allElements = {};
        var textLog = {};
        $('body').find('*').each(function(idx, el) {
            var originalCs = window.getComputedStyle(this);
            var originalText = $(this).text().replace(/\n\s+\n/g,'\n\n').replace(/ \s+ /g,' ');
            var outerHTML = this.outerHTML;
            var outerTag = this.cloneNode(false).outerHTML
            var oW = originalCs.width.replace('px', '');
            var oH = originalCs.height.replace('px', '');

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
                'html': outerHTML,
                'tag': outerTag,
                'original-text': originalText.trim(),
                'original-width': parseFloat(oW),
                'original-height': parseFloat(oH),
                'visible': visible,
                'in-viewport': inViewport,
                'text': text.trim(),
                'width': 0,
                'height': 0,
            };
        });

        var elIdxs = Object.keys(allElements).reverse();
        for (var i = 0; i < elIdxs.length; i++) {
            var idx = elIdxs[i];
            var text = textLog[idx]['text'];

            if (allElements[idx].childElementCount > 0) {
                for(var c=0; c<allElements[idx].childElementCount; c++) {
                    $(allElements[idx].children[c]).remove();
                }

                try {
                    text = $(this).text().trim();
                } catch(ex) {}
            }

            if (text.length > 0) {
                // Make element not wrapped
                $(allElements[idx]).css('position', 'fixed').css('top', '0px')
                    .css('left', '0px').css('width', 'auto').css('height', 'auto')
                    .css('white-space', 'nowrap');

                var cs = window.getComputedStyle(allElements[idx]);
                textLog[idx]['width'] = parseFloat(cs.width.replace('px', '')) || 0;
                textLog[idx]['height'] = parseFloat(cs.height.replace('px', '')) || 0;

                // Put back original element
                $(allElements[idx]).replaceWith(textLog[idx]['html']);
            }

            delete textLog[idx]['html'];
        }

        var arrTextLogs = [];
        var elIdxs = Object.keys(textLog);
        for (var i = 0; i < elIdxs.length; i++) {
            idx = elIdxs[i];
            arrTextLogs.push(JSON.stringify(textLog[idx]));
        }

        return arrTextLogs;
    });

    fs.write(resourceTextFile, textLog.join('\n'), "wb");
    if (logLevel <= Log.INFO) console.log('Processing text --> creating ' + resourceTextFile);
}

function calculateImportance(rule) {
    var importance = 0;

    if(rule == undefined) {
    } else if(rule.match(/^\..*/i)) {
        importance += page.evaluate(getNumElementsByClass, rule);
    } else if(rule.match(/^#.*/i)) {
        var theArr = rule.split('#');
        var theArr2 = theArr[1].split(' ');
        var theGuy = theArr2[0];
        importance += page.evaluate(getNumElementByID, theGuy);
    } else if(rule.match(/.*#.*/i)) {
        importance += page.evaluate(getNumElementByID, rule);
    } else if(rule.match(/[a-zA-Z]*\..*/g)) {
        var theArr = rule.split('.');
        importance += page.evaluate(getNumElementsByTagAndClass, theArr[0], theArr[1]);
    } else if(!(rule.match(/\./ig))) {
        importance += page.evaluate(getNumElementsByTag, rule);
    } else {

    }

    return importance;
}

function getNumElementsByClass(className) {
    var counter = 0;
    var elems = document.getElementsByTagName('*');
    for (var i = 0; i < elems.length; i++) {
        if((' ' + elems[i].className + ' ').indexOf(' ' + className + ' ') > -1) {
            counter++;
        }
    }
    return counter;
}

function getNumElementByID(id) {
    var theThing = document.getElementById(id);
    if(theThing == null)
        return 0;
    return 1;
}

function getNumElementsByTagAndClass(tagName, className) {
    var counter = 0;
    var elems = document.getElementsByTagName(tagName);
    for (var i = 0; i < elems.length; i++) {
        if((' ' + elems[i].className + ' ').indexOf(' ' + className + ' ') > -1) {
            counter++;
        }
    }
    return counter;
}

function getNumElementsByTag(tagName) {
    return document.getElementsByTagName(tagName).length;
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
