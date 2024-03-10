  function checkDamageUriM(uri, onFinished) {
    $.get('/memento/damage', { 'uri' : uri }, function(result) {
      // Append URI in 1st level
      // Images
      var olUrlImgs = $('#images ol.uri');
      if(olUrlImgs.length == 0) {
        olUrlImgs = $('<ol>').attr('class', 'uri').appendTo($('#images'));
      }
      var liUrlImg = $('<li>').appendTo(olUrlImgs);
      $('<div>').html(uri).appendTo(liUrlImg);
      var olImgUrls = $('<ol>').appendTo(liUrlImg);

      // Csses
      var olUrlCsses = $('#csses ol.uri');
      if(olUrlCsses.length == 0) {
        olUrlCsses = $('<ol>').attr('class', 'uri').appendTo($('#csses'));
      }
      var liUrlCss = $('<li>').appendTo(olUrlCsses);
      $('<div>').html(uri).appendTo(liUrlCss);
      var olCssUrls = $('<ol>').appendTo(liUrlCss);

      // result is an object, containing keys: images, csses
      for(var key in result) {
        val = result[key];

        if(key == 'images') {
          val.forEach(function(img) {
            var li = $('<li>').appendTo(olImgUrls);

            // Title = URI
            var title = $('<div>').appendTo(li);
            $('<span>').html(img['url']).appendTo(title);
            $('<span>').html('status_code' in img ? img['status_code'][0] : '').appendTo(title);

            var detail = $('<ul>').appendTo(li);

            // Detail - content_type
            var liDetail = $('<li>').appendTo(detail)
            $('<span>Content-Type</span><span>:</span>').appendTo(liDetail)
            $('<span>'+ img['content_type'] +'</span>').appendTo(liDetail)

            // Detail - rectangles
            var liDetail = $('<li>').appendTo(detail)
            $('<span>Rectangles</span><span>:</span>').appendTo(liDetail)
            var rectangles = [];
            img['rectangles'].forEach(function(rect) {
              rectangles.push('Left: ' + rect['left'] + ' px, Top: ' + rect['top'] +
                ' px, Width: ' + rect['width'] + ' px, Height: ' + rect['height']);
            });
            $('<span>'+ rectangles.join('<br/>') +'</span>').appendTo(liDetail)
          });
        }

        else if(key == 'csses') {
          val.forEach(function(css) {
            var li = $('<li>').appendTo(olCssUrls);

            // Title = URI
            var title = $('<div>').appendTo(li);
            $('<span>').html(css['url']).appendTo(title);
            $('<span>').html('status_code' in css ? css['status_code'][0] : '').appendTo(title);

            var detail = $('<ul>').appendTo(li);

            // Detail - rules
            var liDetail = $('<li>').appendTo(detail)
            $('<span>Rules Selector</span><span>:</span>').appendTo(liDetail)
            $('<span>'+ css['rules_tag'].join(', ') +
              ' (Total '+ css['rules_tag'].length +')' +'</span>').appendTo(liDetail);

            // Detail - importance
            var liDetail = $('<li>').appendTo(detail)
            $('<span>Importance</span><span>:</span>').appendTo(liDetail)
            $('<span>'+ css['importance'] +'</span>').appendTo(liDetail)
          });
        }
      }

      // Call onFinished callback
      onFinished(uri, result)
    }, 'json');
  }
