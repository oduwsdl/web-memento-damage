/**
Test cmd:

phantomjs --local-to-remote-url-access=yes rasterize.js "[URL]" 
"./junk.png" "./junk.html" "./junk.missing"

phantomjs --local-to-remote-url-access=yes rasterize.js "http://192.168.1.7/mementoImportance/www.cs.odu.edu/" 
"./csjunk.png" "./csjunk.html" "./csjunk.missing"
/**/

var system = require('system');
var fs = require('fs');
var server = require('webserver').create();
var theresources = [];
var index = 0;
var thecodes = [];
var theurls = [];

var page = require('webpage').create(),
    address, output, size;

page.settings.resourceTimeout = 50000; // 50 seconds
page.onResourceTimeout = function(e) {
  console.log(e.errorCode);   // it'll probably be 408 
  console.log(e.errorString); // it'll probably be 'Network timeout on resource'
  console.log(e.url);         // the url whose request timed out
};

if (system.args.length < 4 || system.args.length > 5) {
    console.log('Usage: rasterize.js URL png html logFile');
    phantom.exit();
} else {
    address = system.args[1];
    output = system.args[2];
    logLoc = system.args[4];
    page.viewportSize = { width: 1024, height: 777 }; 
    //page.viewportSize = { width: 600, height: 600 };

	//create the file
	fs.write(system.args[4], "", "w");



	/**header monitoring**/
	page.onResourceRequested = function (req) {
		theresources[req.id] = req.url;
		//var logentry = 'requested: ' + JSON.stringify(req, undefined, 4);
		//fs.write(phantom.args[3], logentry, "a");
		    //console.log(theresources[req.id]);

		//console.log('requested: ' + JSON.stringify(req, undefined, 4));

	    };

	    page.onResourceReceived = function (res) {
		var temp = res.url;
		var other = temp.split("/");
		temp = other[2];

		var temp2 = address;
		var other = temp2.split("/");
		temp2 = other[2];
		theresources[res.id] = theresources[res.id] + ", " + res.status;

		var found = 0;
		for(var j = 0; j < theurls.length; j++)
		{
			if(theurls[j] == res.url)
			{
				found = 1;
			}
		}
		if(!found)
		{
			theurls[index]=res.url;
			thecodes[index]=res.status;
			//console.log("done " + theurls[index] + " ==> " + thecodes[index] + "\n"); 
			index++;
		}

		//fs.write(phantom.args[3], res.url + ", " + res.status + "\n", "a");

		//console.log(res.status);
		/**/
	    };
	/**end header monitoring**/


    page.open(address, function (status) {

        if (status !== 'success') {
            console.log('Unable to load the address!');
        } else {


            window.setTimeout(function () {
		console.log("written to " + output + "\n\n");
                page.render(output);

		var pageContent = page.evaluate(function() { 
		    var content = document.body.parentElement.outerHTML; 
		    return content;
		    //console.log("content written");
		});

		/////////////////////////////////////////////////////////

		var sizeArr = page.evaluate(function () {
		     var pageWidth = document.body.clientWidth;
		     var pageHeight = document.body.clientHeight;

		     return [pageWidth, pageHeight];
		  });


		console.log("Starting the " + index + " memento evals...\n\n");

		for(var i = 0; i < index; i++)
		{
			var myurl = theurls[i];
			var mycode = thecodes[i];

			console.log("URL, code: " + i + " ==> " + myurl + ", " + mycode);
			

			/**/	
			//console.log("size: 404!!!\n");
			var theInfo = searchImg("img", myurl);
	
			if(!(theInfo == ""))
			{
				//console.log(myurl + ", img, " + theInfo + "[" + sizeArr + "]" + "\n");
				fs.write(system.args[4], myurl + ", img, " + theInfo + ", " + "[" + sizeArr + "]" + ", " + mycode + "\n", "a");
			}
			else
			{
				if(myurl.endsWith(".png") || myurl.endsWith(".jpeg") || myurl.endsWith(".jpg")
					|| myurl.endsWith(".bmp") || myurl.endsWith(".tiff"))
				{
					fs.write(system.args[4], myurl + ", img, " + "[-1,-1], [-1,-1]" + ", " + "[" + sizeArr + "]" + ", " + mycode + "\n", "a");
				}
				else if((myurl.endsWith(".css")))
				{
				}
				else if(
					(myurl.endsWith(".mpeg"))
					|| (myurl.endsWith(".mp4"))
					|| (myurl.endsWith(".wmv"))
					|| (myurl.endsWith(".flv"))
					|| (myurl.endsWith(".swf"))
					|| (myurl.endsWith(".3g2"))
					|| (myurl.endsWith(".3gp"))
					|| (myurl.endsWith(".asf"))
					|| (myurl.endsWith(".asx"))
					|| (myurl.endsWith(".avi"))
					|| (myurl.endsWith(".m4v"))
					|| (myurl.endsWith(".mov"))
					|| (myurl.endsWith(".mpg"))
					|| (myurl.endsWith(".rm"))
					|| (myurl.endsWith(".srt"))
					|| (myurl.endsWith(".vob"))
					//|| (myurl.endsWith("."))
					)
				{
					var theInfo2 = searchImg("img", myurl);

					if(!(theInfo2 == ""))
					{
						fs.write(system.args[4], myurl + ", multimedia, " + theInfo2 
							+ ", " + "[" + sizeArr + "]" + ", " + mycode + "\n", "a");
					}
					else
					{
						fs.write(system.args[4], myurl + ", multimedia, " 
							+ "[-1,-1], [-1,-1]" + ", " + "[" + sizeArr + "]" 
							+ ", " + mycode + "\n", "a");
					}
				}
				else
				{
					fs.write(system.args[4], myurl + ", other, " + mycode + "\n", "a");					
				}
			}
			
			if(mycode == 404)
			//if(2 < 3)
			{
				
			}
			else
			{
				 //200
			}
			/**/

		}
		/**/


		/////////////////////////////////////////////////////////




		var numSheets = page.evaluate(function ()
		{	
			var theStyles = document.styleSheets;
			return theStyles.length;
		});

		var sheetNames = page.evaluate(function ()
		{	
			var theStyles = document.styleSheets;
			var theNames = Array();
			for(var i = 0; i < theStyles.length; i++)
			{
				if(theStyles[i].href == null)
				{
					theNames.push("[INTERNAL]");
				}
				else
				{
					theNames.push(theStyles[i].href);
				}
			}
			return theNames;
		});

		console.log("\n\n=============\nCSSing\n============\n\n" + numSheets + "\n\n");

		var totalImp = 0;
		for(var i = 0; i < numSheets; i++)
		{
			var importance = searchCSS(pageContent, i);
			console.log("CSS importance " + sheetNames[i] + ": " + importance + "\n\n");
			fs.write(system.args[4], sheetNames[i] + ", " + importance + ", 404\n", "a");
			totalImp += importance;
		}
		    fs.write(system.args[3], pageContent, "w");
		    //console.log(pageContent);

		fs.write("./dataFiles/tagNums.csv", myurl + ", " + totalImp + "\n", "a");

		/**
		fs.write(phantom.args[3], "", "w");
		theresources.forEach(function (key, val) {
			//console.log(val + ', ' + key);
			fs.write(phantom.args[3], val + ", " + key + "\n", "a");
		});
		/**/
		//fs.write(phantom.args[3], theresources[res.id], "a");
                phantom.exit();
            }, 200);
        }
    });

}


function findPos(obj) {
        var curleft = curtop = 0;
        if (obj.offsetParent) {
		do {
		                curleft += obj.offsetLeft;
		                curtop += obj.offsetTop;
		} while (obj = obj.offsetParent);
        	return [curleft,curtop];
	}
}

function getImgSrcJUNK()
{
	var imgs = document.getElementsByTagName("img");
	console.log("Imgs obj: " + imgs[0]  +" \n\n");
	for(var i = 0; i < imgs.length; i++)
	{
		console.log("Image: " + imgs[i] + "\n");
	}
}

function getImgSrc()
{
      var imagesURLs = page.evaluate(function ()
      {
        var documentImages = [];
	var imagesCount = document.getElementsByTagName("img").length;
	//var imagesCount = document.images.length;
	var index = 0;

        while (index < imagesCount)
        {
           documentImages.push(document.images[index].src);

          index++;
        }
	
        return documentImages;
      });

      return imagesURLs;
}

function getImgSize()
{
	var imagesURLs = page.evaluate(function ()
      {
        var documentImages = [], imagesCount = document.images.length, index = 0;

        while (index < imagesCount)
        {
            documentImages.push(document.images[index].width + "," + document.images[index].height);

          index++;
        }

        return documentImages;
      });

	return imagesURLs;
}

function getImgPos()
{
	var imagesURLs = page.evaluate(function ()
      {
        var documentImages = [], imagesCount = document.images.length, index = 0;

        while (index < imagesCount)
        {
		var obj = document.images[index];
		var pos = [];
	    	var curleft = curtop = 0;
		if (obj.offsetParent) {
			do {
				        curleft += obj.offsetLeft;
				        curtop += obj.offsetTop;
			} while (obj = obj.offsetParent);
			pos = [curleft,curtop];
		}
		
            documentImages.push(pos);


          index++;
        }

        return documentImages;
      });

	return imagesURLs;
}

function printall()
{
	

	return imagesURLs;
}

/**/
function searchImg(tagName, source)
{
	var imgSrcArr = getImgSrc();
	var imgHWArr = getImgSize();
	var imgPosArr = getImgPos();

	//sleep(5);

	//var temp = source.split("/");
	//source = temp[temp.length-1]

	console.log("Searching for " + imgSrcArr.length + ", "  + source + "\n");

	for(var i = 0; i < imgSrcArr.length; i++)
	{
		//console.log(source + "\n -vs- \n" + imgSrcArr[i] + "\n\n\n");
		if(!(source.search(imgSrcArr[i]) >= 0))
		{
			//console.log("Not found");
		}
		else
		{
			//console.log("found\n");
			//console.log("FOUND!! " + imgSrcArr[i] + " is " + imgHWArr[i] + " && " + imgPosArr[i] + "\n");

			return "[" + imgHWArr[i] + "], [" + imgPosArr[i]  + "]";
		}
	}
        //phantom.exit();

	/**
	if (!(target==undefined))
	{
		var pos = findPos(target);
		var size = [target.width,target.height];
		console.log("pos // size: " + pos + " // " + size);
		return "[" + size + "], [" + pos  + "]";
	}
	/**/

	return "";
}
/**/

function searchCSS(content, j)
{
	var importance = 0;
	//console.log("lets eval...\n");
	/**/
	var cssProps = page.evaluate(function (j)
	{	
		//https://gist.github.com/n1k0/1501173y();
		//console.log("hola justin\n");
		var theRules = new Array();
		var toReturn = new Array();

		var theStyles = document.styleSheets;

		/**/
		//var j= 0;
		//for(var j = 0; j < theStyles.length; j++)
		//{
			if (theStyles[j].cssRules)
			{
			    	theRules = theStyles[j].cssRules;
				for(var i=0; i < theRules.length; i++)
				{
					toReturn.push(theRules[i].selectorText);
				}
			}
			else if (theStyles[j].rules)
			{
			    	theRules = theStyles[j].rules;
				for(var i=0; i < theRules.length; i++)
				{
					toReturn.push(theRules[i].selectorText);
				}
			}
		//}
		/**/
		return toReturn;
		
	}, j);
	/**/
	//console.log("no more eval: " + cssProps + "...\n");

	if(cssProps == null)
	{
		return 0;
	}
	
	for(var i=0; i < cssProps.length; i++)
	{
		if(cssProps[i].match(/^\..*/i))
		{
			var num = getNumClass(cssProps[i], content);
			importance += num;
			//console.log(i + ": " + num + " => " + cssProps[i] + " is a class-only style\n");			
		}
		else if(cssProps[i].match(/^#.*/i) || cssProps[i].match(/.*#.*/i))
		{
			if(cssProps[i].match(/.*#.*/i))
			{	
				var theArr = cssProps[i].split("#");
				var theArr2 = theArr[1].split(" ");
				var theGuy = theArr2[0];
				var num = getNumID(theGuy);	
				importance += num;	
			}
			else
			{
				var num = getNumID(cssProps[i]);	
				importance += num;
			}		
			//console.log(i + ": " + num + " => " + cssProps[i] + " is an id\n");
		}
		else if(cssProps[i].match(/[a-zA-Z]*\..*/g))
		{
			var theArr = cssProps[i].split(".");
			var num = getNumTagByClass(theArr[0], theArr[1], content);			
			importance += num;
			//console.log(i + ": " + num + " => " + cssProps[i] + " has both\n");
		}
		else if(!(cssProps[i].match(/\./ig)))
		{
			var num = getNumTags(cssProps[i]);
			importance += num;
			//console.log(i + ": " + num + " => " + cssProps[i] + " is a tag only style\n");	
		}
		else
		{
			//console.log(i + ": " + cssProps[i] + " don't know what this is\n");
		}
	}

	/*examples:*
	var tagName = 'a';
	console.log("How many a?\n");
	var num = getNumTags(tagName);
	console.log("This many: " + num + "\n\n");

	var tagName = 'paragraph_style';
	console.log("How many paragraph_style?\n");
	var num = getNumClass(tagName, content);
	console.log("This many: " + num + "\n\n");

	var tagName = "widget1";
	console.log("How many widget1?\n");
	var num = getNumID(tagName);
	console.log("This many: " + num + "\n\n");
	/**/

	//console.log("the classes:...\n");
	var theClasses = getAllClasses(content);

	/**
	console.log("we got " + theClasses.length + "...\n");
	for(var i = 0; i < theClasses.length; i++)
	{
		console.log("class " + i + ": " + theClasses[i] + "\n");
	}
	/**/

	//phantom.exit();

	/**
	*For the CSS matching:
	*look for number of tags with a named class that doesn't exist
	*look for number of tags without a style assigned to them
	*look for nav panels, headers, footers out of place.
	**assumes we can identify nav panels, headers, footers.
	*Look for lots of white space.
	/**/
	return importance;
}

/**/
function getNumTags(tagName)
{
	var num = page.evaluate(function(tagName) {
	    return document.getElementsByTagName(tagName).length;
	}, tagName);

	return num;
}
function getNumClass(tagName, content)
{
	var num = page.evaluate(function(tagName) {
		/**/
		var counter = 0;
		var elems = document.getElementsByTagName('*');
		for (var i = 0; i < elems.length; i++) {
			if((' ' + elems[i].className + ' ').indexOf(' ' + tagName + ' ') > -1) 
			{
				counter++;
			}
		}
		/**/
		return counter;
	}, tagName);

	return num;
}
function getNumTagByClass(tagName, styleName, content)
{
	var num = page.evaluate(function(tagName, styleName) {
		/**/
		var counter = 0;
		var elems = document.getElementsByTagName(tagName);
		for (var i = 0; i < elems.length; i++) {
			if((' ' + elems[i].className + ' ').indexOf(' ' + styleName + ' ') > -1) 
			{
				counter++;
			}
		}
		/**/
		return counter;
	}, tagName, styleName);

	return num;
}
function getNumID(tagName)
{
	var num = page.evaluate(function(tagName) {
	    var theThing = document.getElementById(tagName);
	    if(theThing == null)
		return 0;
	    return 1;
	}, tagName);

	return num;
}
/**/

function getAllClasses(content)
{
	var num = page.evaluate(function() {
		/**/
		var myClasses = Array();
		var elems = document.getElementsByTagName('*');
		for (var i = 0; i < elems.length; i++) {
			if((elems[i].className == "") || (elems[i].className == null))
			{
				//do nothing
			}
			else
			{
				myClasses.push(elems[i].className);
			}
		}
		/**/
		return myClasses;
	});

	return num;
}

String.prototype.endsWith = function(suffix) {
    suffix = suffix.toLowerCase();
    return this.indexOf(suffix, this.length - suffix.length) !== -1;
};
