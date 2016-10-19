var Nightmare = require('nightmare'),
    harPlugin = require('nightmare-har-plugin')
    vo = require('vo');

harPlugin.install(Nightmare)

function * run() {
    var nightmare = Nightmare(Object.assign(harPlugin.getDevtoolsOptions(), {
        show: true,
        width: 1024,
        height: 768
    }));

    yield nightmare
        .goto('https://web.archive.org/web/19990125094845/http://www.dot.state.al.us/')
        .wait('body');

    yield nightmare.getHAR()
        .then((result) => console.log(JSON.stringify(result)))
        .catch((error) => console.error(error));

    var dimensions = yield nightmare
        .evaluate(function() {
            var body = document.querySelector('body');
            return { 
                height: body.scrollHeight,
                width:body.scrollWidth
            }
        });
    
    yield nightmare.viewport(dimensions.width, dimensions.height)
        .wait(1000)
        .screenshot('./test.png');

    yield nightmare.end();
}

vo(run)(function() {
    console.log('done');
});
