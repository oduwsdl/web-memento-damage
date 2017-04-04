$.fn.extend({
    isVisible: function() {
        if ( $(this).css('display') == 'none' ){
            return false;
        }
        else if( $(this).css('visibility') == 'hidden' ){
            return false;
        }
        else if( $(this).css('opacity') == '0' ){
            return false;
        }
        else if( $(this).outerWidth(false) == 0 ){
            return false;
        }
        else if( $(this).outerHeight(false) == 0 ){
            return false;
        }
        else if( this.tagName == 'script' ){
            return false;
        }
        else if( this.tagName == 'style' ){
            return false;
        }
        else{
            return true;
        }
    }
});