var arrayWithElements = new Array();

function clickListener(e) 
{   
    var clickedElement=(window.event)
                        ? window.event.srcElement
                        : e.target,
        tags=document.getElementsByTagName(clickedElement.tagName);

    //alert("position: " + findPos(clickedElement));
    searchBySrc("img", "http://localhost/mementoImportance/odoodledoos.com/OdoodleDoos/Welcome_files/shapeimage_4.png")

    for(var i=0;i<tags.length;++i)
    {
      if(tags[i]==clickedElement)
      {
        arrayWithElements.push({tag:clickedElement.tagName,index:i}); 
        //alert(arrayWithElements);
      }    
    }
}

function clicker()
{
        //alert('justin');
        $(document).on('click', 'a', function(e) {
            return false;
        });

        document.onclick = clickListener;
        //alert('added clicker');

        //alert("width: " + $(window).width() + ", height: " + $(window).height());
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
/**/
function searchBySrc(tagName, source)
{
	//alert('justin');
	var allImages = document.getElementsByTagName(tagName);
	var target;
	for(var i = 0, max = allImages.length; i < max; i++)
	{
	    var theSrc = allImages[i].getAttribute("src");
		//alert("Comparing " + theSrc + " and " + source);
	    if (source.search(theSrc) >= 0){
		//alert("match found...");
	       target = allImages[i];
	       break;
	    }
	}
	
	var pos = findPos(target);
	var size = [target.width,target.height];
	alert("pos // size: " + pos + " // " + size);
}
/**/


//in body:  onload="clicker()"
//need to also include jquery:  <script src="http://ajax.googleapis.com/ajax/libs/jquery/1.7.1/jquery.min.js"></script>

