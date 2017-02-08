!function(a,b){function c(b){var c,d=a("<div></div>").css({width:"100%"});return b.append(d),c=b.width()-d.width(),d.remove(),c}function d(e,f){var g=e.getBoundingClientRect(),h=g.top,i=g.bottom,j=g.left,k=g.right,l=a.extend({tolerance:0,viewport:b},f),m=!1,n=l.viewport.jquery?l.viewport:a(l.viewport);n.length||(console.warn("isInViewport: The viewport selector you have provided matches no element on page."),console.warn("isInViewport: Defaulting to viewport as window"),n=a(b));var o=n.height(),p=n.width(),q=n[0].toString();if(n[0]!==b&&"[object Window]"!==q&&"[object DOMWindow]"!==q){var r=n[0].getBoundingClientRect();h-=r.top,i-=r.top,j-=r.left,k-=r.left,d.scrollBarWidth=d.scrollBarWidth||c(n),p-=d.scrollBarWidth}return l.tolerance=~~Math.round(parseFloat(l.tolerance)),l.tolerance<0&&(l.tolerance=o+l.tolerance),0>=k||j>=p?m:m=l.tolerance?h<=l.tolerance&&i>=l.tolerance:i>0&&o>=h}String.prototype.hasOwnProperty("trim")||(String.prototype.trim=function(){return this.replace(/^\s*(.*?)\s*$/,"$1")});var e=function(b){if(1===arguments.length&&"function"==typeof b&&(b=[b]),!(b instanceof Array))throw new SyntaxError("isInViewport: Argument(s) passed to .do/.run should be a function or an array of functions");for(var c=0;c<b.length;c++)if("function"==typeof b[c])for(var d=0;d<this.length;d++)b[c].call(a(this[d]));else console.warn("isInViewport: Argument(s) passed to .do/.run should be a function or an array of functions"),console.warn("isInViewport: Ignoring non-function values in array and moving on");return this};a.fn["do"]=function(a){return console.warn("isInViewport: .do is deprecated as it causes issues in IE and some browsers since it's a reserved word. Use $.fn.run instead i.e., $(el).run(fn)."),e(a)},a.fn.run=e;var f=function(b){if(b){var c=b.split(",");return 1===c.length&&isNaN(c[0])&&(c[1]=c[0],c[0]=void 0),{tolerance:c[0]?c[0].trim():void 0,viewport:c[1]?a(c[1].trim()):void 0}}return{}};a.extend(a.expr[":"],{"in-viewport":a.expr.createPseudo?a.expr.createPseudo(function(a){return function(b){return d(b,f(a))}}):function(a,b,c){return d(a,f(c[3]))}}),a.fn.isInViewport=function(a){return this.filter(function(b,c){return d(c,a)})}}(jQuery,window);

var allElements = {};
var textLog = {};
$('body').find('*').each(function(idx, el) {
    var originalCs = window.getComputedStyle(this);
    var originalText = $(this).text();
    var outerHTML = this.outerHTML;
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

    try {
        var text = $(this).contents().not($(this).children()).text();
    } catch (ex) {
        var text = "";
    }

    textLog[idx] = {
        'html': outerHTML,
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

var elIdxs = Object.keys(allElements);
for (var i = 0; i < elIdxs.length; i++) {
    idx = elIdxs[i];
    if (textLog[idx]['text'].length > 0) {
        // Make element not wrapped
        $(allElements[idx]).css('position', 'fixed').css('top', '0px')
            .css('left', '0px').css('width', 'auto').css('white-space', 'nowrap');

        var cs = window.getComputedStyle(allElements[idx]);
        textLog[idx]['width'] = parseFloat(cs.width.replace('px', ''));
        textLog[idx]['height'] = parseFloat(cs.height.replace('px', ''));

        // Put back original element
        $(allElements[idx]).replaceWith(textLog[idx]['html']);
    }
}
