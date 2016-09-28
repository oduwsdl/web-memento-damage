/**
Test cmd:

phantomjs --local-to-remote-url-access=yes rasterize.js "[URL]" 
"./junk.png" "./junk.html" "./junk.missing"

phantomjs --local-to-remote-url-access=yes rasterize.js "http://192.168.1.7/mementoImportance/www.cs.odu.edu/" 
"./csjunk.png" "./csjunk.html" "./csjunk.missing"
/**/

var fs = require('fs');
var server = require('webserver').create();
var theresources = [];

var page = require('webpage').create(),
    address, output, size;

if (phantom.args.length < 1 || phantom.args.length > 1) {
    console.log('Usage: rasterize.js URL filename logFile');
    phantom.exit();
} else {
    address = phantom.args[0];
    page.viewportSize = { width: 1024, height: 777 }; 
    //page.viewportSize = { width: 600, height: 600 };

	//create the file



    page.open(address, function (status) {

        if (status !== 'success') {
            console.log('Unable to load the address!');
        } else {
            window.setTimeout(function () {
                page.render(output);

		var pageContent = page.evaluate(function() { 
		    var content = document.body.parentElement.outerHTML; 
		    return content;
		    //console.log("content written");
		});

		
		//console.log("opening...\n\n");
		var bgCol = page.evaluate(function ()
		{	
			var theColor = document.body.style.backgroundColor;
			return theColor;
		});
		console.log(bgCol + "\n");
		phantom.exit();

            }, 200);
        }
    });
}



