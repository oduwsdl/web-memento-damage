var system = require('system');
var fs = require('fs');
//var path = require('./path.js');
var page = require('webpage').create();
var networkResources = {}

// Import md5 from CryptoJS to hash URI
phantom.injectJs('md5.js')
// Import underscore.js to make array unique
phantom.injectJs('underscore.js')

// Set start time
var starttime = Date.now()

// If number of arguments after crawl.js is not 2, show message and exit phantomjs
if (system.args.length != 5) {
    console.log('Usage: phantomjs crawl.js <URI> <screenshot_file> <html_file> <log_file>');
    phantom.exit(1);
}

// Else, continue opening URI
else {
    // use 1st param after crawl.js as URL input and 2nd param as output
    url = system.args[1];
    screenshotFile = system.args[2];
    htmlFile = system.args[3];
    logFile = system.args[4];
    
    //outputDir = system.args[2];

    // Set timeout on fetching resources to 10 seconds (can be changed)
    page.settings.resourceTimeout = 10000;
    page.onResourceTimeout = function(e) {
        console.log('Resource', e.url, 'timeout.', e.errorCode, e.errorString);
    };

    // Use browser size 1024x768 (to be used on screenshot)
    page.viewportSize = { width: 1024, height: 768 };
    
    // Resource is similiar with all listed in developer tools -> network tab -> refresh
    page.onResourceReceived = function (res) {
        resUrl = res.url;
        console.log('Resource received', resUrl);
        
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
            'content_type' : res.contentType, 
            'headers' : headers,             
        }
        
        var networkResourcesKeys = Object.keys(networkResources);
        if(! _.contains(networkResourcesKeys, resUrl)) {
            networkResources[resUrl] = resource;
        }
    };

    // Open URI
    page.open(url, function (status) {
        if (status !== 'success') {
            console.log('Unable to load the url', url);
            phantom.exit(1);
        } else {
            // After page is opened, process page.
            // Use setTimeout to delay process
            // Timeout in ms, means 200 ms
            window.setTimeout(function () {
                processPage(url, screenshotFile, htmlFile, logFile);
                
                // Set finished time
                var finishtime = Date.now()
                
                // Show message that crawl finished, and calculate executing time
                console.log('Crawl finished in', (finishtime - starttime), 'miliseconds');

                // Show bgcolor
                console.log(JSON.stringify({'background_color' : getBackgroundColor()}));
                phantom.exit();
            }, 200);
        }
    });
    
}

function processPage(url, screenshotFile, htmlFile, resourceFile) {
    var hashedUrl = md5(url);
    
    // Save screenshot
    page.render(screenshotFile);
    console.log('Screenshot is saved in', screenshotFile)
    
    // Save html using fs.write
    // DOM selection or modification always be done inside page.evaluate
    var html = page.evaluate(function() { 
        return document.body.parentElement.outerHTML;
    });
    fs.write(htmlFile, html, "w");
    console.log('HTML source of page is saved in', htmlFile)
    
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
    console.log('Network resources is saved in', resourceFile)

    // Split dir and filename
    var resourceBasename = resourceFile.replace('/.*//', '' ); //path.basename(resourceFile, '.log')
    resourceBasename = resourceBasename.replace('.log', '');

    processImages(url, resourceBasename);
    processCsses(url, resourceBasename);
}

function processImages(url, resourceBasename) {
    var hashedUrl = md5(url);

    // Get images using document.images
    // document.images also can be execute in browser console
    var images = page.evaluate(function () {
        var documentImages =  document.images;
        var allImages = [];

        for(var i=0; i<documentImages.length; i++) {
            var docImage = documentImages[i];

            // Calculate top left position
            var obj = docImage;
            var curleft = 0, curtop = 0;
            if (obj.offsetParent) {
                do {
                    curleft += obj.offsetLeft;
                    curtop += obj.offsetTop;
                } while (obj = obj.offsetParent);
            }

            // Create json containing url and rectangle
            var jsonImage = {
                'url' : docImage['src'],
                'viewport_size' : [document.body.clientWidth, document.body.clientHeight],
                'rectangle' : {
                    'width' : docImage['width'],
                    'height' : docImage['height'],
                    'top' : curtop,
                    'left' : curleft,
                },
            };

            // Append to all images
            allImages.push(jsonImage);
        }

        return allImages;
    });

    // Check images url == resource url, append position if same
    var networkImages = {};
    var networkResourcesKeys = Object.keys(networkResources);
    for(var i=0; i<images.length; i++) {
        var image = images[i];

        idx = _.indexOf(networkResourcesKeys, image['url']);
        if(idx >= 0) {
            if(_.indexOf(networkImages, image['url']) < 0) {
                networkImages[image['url']] = networkResources[networkResourcesKeys[idx]]
            }

            networkImages[image['url']]['viewport_size'] = image['viewport_size']

            if('rectangles' in networkImages[image['url']]) {
                networkImages[image['url']]['rectangles'].push(image['rectangle'])
            } else {
                networkImages[image['url']]['rectangles'] = []
            }
        }
    }

    // Save all resource images
    // var resourceImageFile = path.join(resourceDir, resourceBasename + '.img.log');
    var resourceImageFile = resourceBasename + '.img.log'

    var networkImagesValues = []
    var networkImagesKeys = Object.keys(networkImages);
    for(r=0; r<networkImagesKeys.length; r++) {
        var value = networkImages[networkImagesKeys[r]];
        networkImagesValues.push(JSON.stringify(value));
    }

    fs.write(resourceImageFile, networkImagesValues.join('\n'), "w");
    console.log('Network resource images is saved in', resourceImageFile)
}

function processCsses(url, resourceBasename) {
    var hashedUrl = md5(url);

    var csses = page.evaluate(function () {
        // Get all stylesheets. This command also can be run in browser console document.styleSheets
        var documentCsses = document.styleSheets;
        var allCsses = []

        for(var c=0; c<documentCsses.length; c++) {
            var docCss = documentCsses[c];

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
                'rules_tag' : rules_tag,
            };

            allCsses.push(jsonCss);
        }

        return allCsses;
    });

    // Check css url == resource url, append position if same
    var networkCsses = []
    var networkResourcesKeys = Object.keys(networkResources);
    for(var i=0; i<csses.length; i++) {
        var css = csses[i];

        idx = _.indexOf(networkResourcesKeys, css['url']);
        if(idx >= 0) {
            var networkCss = networkResources[networkResourcesKeys[idx]];
            css = _.extend(css, networkCss);
        }

        if('rules_tag' in css) {
            var importance = 0;
            for(var r=0; r<css['rules_tag'].length; r++) {
                var rule = css['rules_tag'][r];
                importance += calculateImportance(rule);
            }
            css['importance'] = importance;

            networkCsses.push(css);
        }
    }

    // Save all resource csses
    // var resourceCssFile = path.join(resourceDir, resourceBasename + '.css.log');
    var resourceCssFile = resourceBasename + '.css.log'

    networkCssValues = []
    for(r=0; r<networkCsses.length; r++) {
        networkCssValues.push(JSON.stringify(networkCsses[r]));
    }

    fs.write(resourceCssFile, networkCssValues.join('\n'), "wb");
    console.log('Network resource csses is saved in', resourceCssFile)
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
        return document.body.style.backgroundColor || 'FFFFFF';
    })
}
