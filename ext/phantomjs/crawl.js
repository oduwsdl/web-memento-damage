if (!String.prototype.endsWith) {
    String.prototype.endsWith = function(searchString, position) {
        var subjectString = this.toString();
        if (typeof position !== 'number' || !isFinite(position) || Math.floor(position) !== position || position > subjectString.length) {
          position = subjectString.length;
        }
        position -= searchString.length;
        var lastIndex = subjectString.indexOf(searchString, position);
        return lastIndex !== -1 && lastIndex === position;
    };
}

var system = require('system');
var fs = require('fs');
//var path = require('./path.js');
var page = require('webpage').create();
var networkResources = {}

page.settings.webSecurityEnabled = false;
// Import md5 from CryptoJS to hash URI
phantom.injectJs('md5.js')
// Import underscore.js to make array unique
phantom.injectJs('underscore.js')
// Import mimetype.js to resolve content-type of 4xx resources
phantom.injectJs('mimetype.js')

// Set start time
var starttime = Date.now()

// If number of arguments after crawl.js is not 2, show message and exit phantomjs
if (system.args.length < 3) {
    console.log('Usage: phantomjs crawl.js <URI> <output_dir>');
    phantom.exit(1);
}

// Else, continue opening URI
else {
    // use 1st param after crawl.js as URL input and 2nd param as output
    url = system.args[1];
    outputDir = system.args[2];

    // Set timeout on fetching resources to 30 seconds (can be changed)
    page.settings.resourceTimeout = 30000;
    page.onResourceTimeout = function(e) {
        console.log('Resource ' + e.url + ' timeout. ' + e.errorCode + ' ' + e.errorString);
    };

    // Use browser size 1024x768 (to be used on screenshot)
    page.viewportSize = { width: 1024, height: 777 };

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
        console.log('CONSOLE: ' + msg + ' (from line #' + lineNum + ' in "' + sourceId + '")');
    };

    // Resource is similiar with all listed in developer tools -> network tab -> refresh
    page.onResourceReceived = function (res) {
        resUrl = res.url;
        console.log('Resource received ' + resUrl + ' (' + res.status + ')');

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

    page.onLoadFinished =  function (status) {
        if (status !== 'success') {
            console.log(JSON.stringify({'crawl-result' : {
              'error' : true,
              'message' : 'Unable to load the url'
            }}));
            phantom.exit(1);
        } else {
            // After page is opened, process page.
            // Use setTimeout to delay process
            // Timeout in ms, means 200 ms
            window.setTimeout(function () {
                if (page.injectJs('jquery-3.1.0.min.js') && page.injectJs('underscore.js')) {
                    processPage(url, outputDir);
                    // Show bgcolor
                    console.log(JSON.stringify({'background_color' : getBackgroundColor()}));

                    // Set finished time
                    var finishtime = Date.now()

                    // Show message that crawl finished, and calculate executing time
                    console.log(JSON.stringify({'crawl-result' : {
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
    page.open(url);

}

function processPage(url, outputDir) {
    processNetworkResources(url, outputDir);
    processHtml(url, outputDir);
    processImages(url, outputDir);
    processMultimedias(url, outputDir);
    processCsses(url, outputDir);
    processScreenshots(url, outputDir);
}

function processNetworkResources(url, outputDir) {
    hashedUrl = md5(url);
    resourceFile = outputDir + '/log/' + hashedUrl + '.log';

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
    console.log('Network resources is saved in ' + resourceFile)
}

function processHtml(url, outputDir) {
    hashedUrl = md5(url);
    htmlFile = outputDir + '/html/' + hashedUrl + '.html';

    // Save html using fs.write
    // DOM selection or modification always be done inside page.evaluate
    var html = page.evaluate(function() {
        return document.body.parentElement.outerHTML;
    });
    fs.write(htmlFile, html, "w");
    console.log('HTML source of page is saved in ' + htmlFile)
}

function processImages(url, outputDir) {
    var hashedUrl = md5(url);
    resourceImageFile = outputDir + '/log/' + hashedUrl + '.img.log';

    // Get images using document.images
    // document.images also can be execute in browser console
    var images = page.evaluate(function () {
        var allImages = {};
        var documentImages = [];

        var images = document.images;
        for(var i=0; i<images.length; i++) documentImages.push(images[i]);
        var frames = window.frames;
        for(var f=0; f<frames.length; f++) {
            images = frames[f].document.images;
            for(var i=0; i<images.length; i++) documentImages.push(images[i]);
        }

        for(var i=0; i<documentImages.length; i++) {
            var docImage = documentImages[i];
            allImages[docImage['src']] = {};
            allImages[docImage['src']]['rectangles'] = []
        }

        for(var i=0; i<documentImages.length; i++) {
            var docImage = documentImages[i];

            // Calculate vieport size
            allImages[docImage['src']]['viewport_size'] = [
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

            allImages[docImage['src']]['rectangles'].push(rectangle);
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
                    networkImages[url]['viewport_size'] = [10,10]
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

    fs.write(resourceImageFile, networkImagesValues.join('\n'), "w");
    console.log('Network resource images is saved in ' + resourceImageFile)
}

function processMultimedias(url, outputDir) {
    var hashedUrl = md5(url);
    resourceVideoFile = outputDir + '/log/' + hashedUrl + '.vid.log';

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

    var viewport_size = page.evaluate(function () {
        return [document.body.clientWidth, document.body.clientHeight];
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

                if(! ('rectangles' in networkVideos[url])) {
                    networkVideos[url]['rectangles'] = []
                }

                networkVideos[url]['url'] = url;
                networkVideos[url]['viewport_size'] = viewport_size;
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

    fs.write(resourceVideoFile, networkVideosValues.join('\n'), "w");
    console.log('Network resource videos is saved in ' + resourceVideoFile)
}

function processCsses(url, resourceBasename) {
    var hashedUrl = md5(url);
    resourceCssFile = outputDir + '/log/' + hashedUrl + '.css.log';

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

        var tmpCsses = document.styleSheets;
        for(t=0; t<tmpCsses.length; t++) allCsses.push(serialize(tmpCsses[t], -1));

        var tmpFrames = window.frames;
        for(f=0; f<tmpFrames.length; f++) {
            var tmpDocument = tmpFrames[f].document;
            if(tmpDocument == undefined) tmpDocument = tmpFrames[f];

            tmpCsses = tmpDocument.styleSheets;
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

    fs.write(resourceCssFile, networkCssValues.join('\n'), "wb");
    console.log('Network resource csses is saved in ' + resourceCssFile)
}

function processScreenshots(url, outputDir) {
    hashedUrl = md5(url);
    screenshotDir = outputDir + '/screenshot/' + hashedUrl;
    screenshotFile = screenshotDir + '.png';

    // Save screenshot
    page.render(screenshotFile);
    console.log('Screenshot is saved in ' + screenshotFile);

    var outerHTMLCsses = page.evaluate(function() {
        outerHTMLCsses = [];

        var tmpCsses = document.styleSheets;
        for(t=0; t<tmpCsses.length; t++) {
            outerHTMLCsses.push({'frame' : -1, 'idx' : t, 'html' : tmpCsses[t].ownerNode.outerHTML});
        }

        var tmpFrames = window.frames;
        for(f=0; f<tmpFrames.length; f++) {
            var tmpDocument = tmpFrames[f].document;
            if(tmpDocument == undefined) tmpDocument = tmpFrames[f];

            tmpCsses = tmpDocument.styleSheets;
            for(t=0; t<tmpCsses.length; t++) {
                outerHTMLCsses.push({'frame' : f, 'idx' : t, 'html' : tmpCsses[t].ownerNode.outerHTML});
            }
        }

        return outerHTMLCsses;
    }) || [];

    outerHTMLCsses.forEach(function(outerHTMLCss) {
        hashedCss = md5(outerHTMLCss['html']);
        screenshotFile = screenshotDir + '/' + hashedCss + '.png';

        // Remove css
        var removed = page.evaluate(function(outerHTMLCss) {
            if(outerHTMLCss['frame'] >= 0) {
                var tmpFrame = window.frames[outerHTMLCss['frame']];
                var tmpDocument = tmpFrame.document;
                if(tmpDocument == undefined) tmpDocument = tmpFrame;
            } else {
                var tmpDocument = document;
            }

            var tmpCss = tmpDocument.styleSheets[outerHTMLCss['idx']];
            if(tmpCss) {
                var tmpCssOwner = tmpCss.ownerNode;
                tmpCssOwner.parentElement.removeChild(tmpCssOwner);
                return true;
            }

            return false
        }, outerHTMLCss);

        // Save screenshot
        page.render(screenshotFile);
        console.log('Screenshot is saved in ' + screenshotFile);

        // Put css back
        if(removed) {
            page.evaluate(function(outerHTMLCss) {
                if(outerHTMLCss['frame'] >= 0) {
                    var tmpFrame = window.frames[outerHTMLCss['frame']];
                    var tmpDocument = tmpFrame.document;
                    if(tmpDocument == undefined) tmpDocument = tmpFrame;
                } else {
                    var tmpDocument = document;
                }

                var parentEl = tmpDocument.getElementsByTagName('head')[0];
                var parentInnerHTML = parentEl.innerHTML;
                parentInnerHTML += outerHTMLCss;

                parentEl.innerHTML = parentInnerHTML;
            }, outerHTMLCss);
        }
    });
}

function processScreenshotsOld(url, outputDir) {
    hashedUrl = md5(url);
    screenshotDir = outputDir + '/screenshot/' + hashedUrl;
    screenshotFile = screenshotDir + '.png';

    // Save screenshot
    page.render(screenshotFile);
    console.log('Screenshot is saved in ' + screenshotFile)

    // Save screenshot for each css lost (simmulation)
    var outerHTMLCsses = page.evaluate(function() {
        outerHTMLCsses = [];

        docCsses = $('style, link[rel="stylesheet"]');
        for(var c=0; c<docCsses.length; c++) {
            outerHTMLCsses.push({'frame' : -1, 'idx' : c, 'html' : docCsses[c].outerHTML});
        }

        frames = $('frame, iframe').contents();
        for(f=0; f<frames.length; f++) {
            docCsses = $(frames[f]).find('style, link[rel="stylesheet"]');
            for(var c=0; c<docCsses.length; c++) {
                outerHTMLCsses.push({'frame' : f, 'idx' : c, 'html' : docCsses[c].outerHTML});
            }
        }

        return outerHTMLCsses;
    }) || [];

    outerHTMLCsses.forEach(function(outerHTMLCss) {
        hashedCss = md5(outerHTMLCss['html']);
        screenshotFile = screenshotDir + '/' + hashedCss + '.png';

        // Remove css
        page.evaluate(function(outerHTMLCss) {
            if(outerHTMLCss['frame'] >= 0) {
              frames = $('frame, iframe').contents();
              for(f=0; f<frames.length; f++) {
                  $(frames[f]).find('style, link[rel="stylesheet"]')[outerHTMLCss['idx']].remove();
              }
            } else {
                $('style, link[rel="stylesheet"]')[outerHTMLCss['idx']].remove();
            }
        }, outerHTMLCss);

        // Save screenshot
        page.render(screenshotFile);
        console.log('Screenshot is saved in ' + screenshotFile);

        // Put css back
        page.evaluate(function(outerHTMLCss) {
            if(outerHTMLCss['frame'] >= 0) {
              frames = $('frame, iframe');
              for(f=0; f<frames.length; f++) {
                  $(outerHTMLCss['html']).appendTo($('head'));
              }
            } else {
                $(outerHTMLCss['html']).appendTo($(frames[f]).find('head'));
            }
        }, outerHTMLCss);
    });
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
