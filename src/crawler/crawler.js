/*
  Web crawler for the Memento Damage project

  Web Science and Digital Libraries research group
  Dept. of Computer Science, Old Dominion University
*/

import { performance } from 'perf_hooks'
import fs from 'fs'
import puppeteer from 'puppeteer'
import sharp from 'sharp'

// Recreating __dirname and __filename for ES6 modules (https://stackoverflow.com/a/55944697/3359239)
import { fileURLToPath } from 'url'
import { dirname } from 'path'
import { exit } from 'process'
import { parseArgs } from 'node:util'

import express from 'express'

// Hyperparameter constants
const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const __replaydir = `${dirname(__dirname)}/replay`

const HTTP_STATUS_CODES = {
  200 : 'OK',
  201 : 'Created',
  202 : 'Accepted',
  203 : 'Non-Authoritative Information',
  204 : 'No Content',
  205 : 'Reset Content',
  206 : 'Partial Content',
  300 : 'Multiple Choices',
  301 : 'Moved Permanently',
  302 : 'Found',
  303 : 'See Other',
  304 : 'Not Modified',
  305 : 'Use Proxy',
  307 : 'Temporary Redirect',
  400 : 'Bad Request',
  401 : 'Unauthorized',
  402 : 'Payment Required',
  403 : 'Forbidden',
  404 : 'Not Found',
  405 : 'Method Not Allowed',
  406 : 'Not Acceptable',
  407 : 'Proxy Authentication Required',
  408 : 'Request Timeout',
  409 : 'Conflict',
  410 : 'Gone',
  411 : 'Length Required',
  412 : 'Precondition Failed',
  413 : 'Request Entity Too Large',
  414 : 'Request-URI Too Long',
  415 : 'Unsupported Media Type',
  416 : 'Requested Range Not Satisfiable',
  417 : 'Expectation Failed',
  418 : "I'm a teapot",
  500 : 'Internal Server Error',
  501 : 'Not Implemented',
  502 : 'Bad Gateway',
  503 : 'Service Unavailable',
  504 : 'Gateway Timeout',
  505 : 'HTTP Version Not Supported'
}
const Log = {
  'DEBUG': 10,
  'INFO': 20,
  'WARN': 30,
  'ERROR': 40,
  'FATAL': 50,
}


/* ---
// Crawler Initialization
--- */
const args = process.argv.slice(2)

// node crawler.js [uri] [warcFile] [cache] [debug] [log_level] [timeout] [viewport]
const options = {
    warcDir: { type: 'string', short: 'W' },
    warcFile: { type: 'string', short: 'w' },
    cache: { type: 'string', short: 'c' },
    debug: { type: 'boolean', short: 'd', default: false },
    log: { type: 'string', short: 'l', default: '60' },
    timeout: { type: 'string', short: 't', default: '60000' },
    viewport: { type: 'string', short: 'v', default: '1920_1080' },
}
let { values, positionals } = parseArgs({ args, options, allowPositionals: true })
let URI = undefined
if (positionals.length == 1 && positionals[0].startsWith('http')) URI = positionals[0]
switch (undefined) { // Handle undefined input states
  case URI:
    console.error('Invalid URI provided'); exit(1)
  case values.cache:
    console.error('No cache directory provided'); exit(1)
  case values.debug:
    values.debug = values.debug || false
  case values.log:
    values.log = 30
  case values.timeout:
    values.timeout = 1000 * 30   // ms
  case values.viewport:
    values.viewport = [1920, 1080]
}

// Input safety checks
if (! URI.startsWith('http')) { console.error('Invalid URI provided'); exit(1) }
if (! fs.statSync(values.cache).isDirectory()) { console.error('Provided cache argument is not a valid directory'); exit(1) }

try {
  values.log = parseInt(values.log)
  if (values.log < 10) { values.log = 10 } else if (values.log > 40) { values.log = 40 }
} catch (e) { console.error(`Error processing log level argument:\n${e.message}`); exit(1) }

try {
  values.timeout = parseInt(values.timeout)
  if (values.timeout < 10) values.timeout = 10
  values.timeout = values.timeout * 1000
} catch (e) { console.error(`Error processing timeout argument:\n${e.message}`); exit(1) }

try {
  let v = values.viewport.split('_')
  values.viewport = [parseInt(v[0]), parseInt(v[1])]
} catch (e) { console.error(`Error processing viewport argument:\n${e.message}`); exit(1) }


const WARC_DIR = values.warcDir,
      WARC_URI = values.warcFile,
      CACHE = values.cache,
        CRAWL_LOG_FILE = CACHE + '/crawl.log',
        DATA_CACHE = CACHE + '/data',
        NET_CACHE = CACHE + '/net',
        PAGE_CACHE = CACHE + '/page',
        SCREENSHOT_CACHE = CACHE + '/screenshots',
      DEBUG = values.debug,
      LOG_LEVEL = values.log,
      TIMEOUT = values.timeout,
      VIEWPORT = values.viewport

let replayServer = null
const WARC_REPLAY_SRV = 'http://localhost:9990'

// Timeouts in milliseconds (default: 60 seconds)
let NAVIGATION_TIMEOUT = 60000,
      RESOURCE_TIMEOUT = 30000

// Initialize log file and logging function
try {
  fs.openSync(CRAWL_LOG_FILE, 'w')
} catch (e) { console.error(`Error opening log file:\n${e.message}`); exit(1) }

const log = (threshold, message) => {
  if (LOG_LEVEL <= threshold) {
    let timestamp = new Date().toISOString()
    let logLabel = Object.keys(Log).find(key => Log[key] === threshold)
    fs.appendFileSync(CRAWL_LOG_FILE, `${timestamp} ${logLabel}: ${message}\n`)

    // if (DEBUG && (threshold == Log.ERROR || threshold == Log.DEBUG)) {
    //   console.log(`${timestamp} ${logLabel}: ${message}`)
    // }
  }
}

log(Log.DEBUG, `Input arguments:\n    URI: ${URI}\n    WARC_URI: ${WARC_URI}\n    WARC_DIR: ${WARC_DIR}\n    Cache: ${CACHE}\n    Debug Mode: ${DEBUG}\n    Log level: ${LOG_LEVEL}\n    Timeout (ms): ${TIMEOUT}\n    Viewport: ${VIEWPORT}`)


/* ---
// Global variables
--- */
let browser = null
// let userAgent = null
let pageSession = null
let page = null
let replayFrame = null

let pageUrl = URI
let navUrls = []
let pageErrors = []

// Network request/response tracking
let cdpRequests = {}
let cdpRequestFailures = {}
let cdpResponses = {}
let redirectMap = {}
let pendingRequests = {}
let lateRequests = {}

let warcLoadTimeout = 30
let abortNewRequests = false


/* ---
// Utility functions
--- */
const sleep = async (ms) => {
  return new Promise(resolve => setTimeout(resolve, ms))
}


const writeJsonlData = (fileName, jsonlData) => {
  if (!fs.existsSync(`${DATA_CACHE}`)) fs.mkdirSync(`${DATA_CACHE}`)

  fs.writeFileSync(`${DATA_CACHE}/${fileName}.jsonl`, jsonlData.join('\n'))
  log(Log.INFO, `Log saved: data/${fileName}.jsonl`)
}


const startReplayServer = () => {
  replayServer = express()
  replayServer.use(express.static(__replaydir))
  replayServer.use(express.static(WARC_DIR))

  replayServer.set('views', `${__replaydir}/views`)
  replayServer.set('view engine', 'ejs')

  replayServer.get('/embed', (req, res) => {
    const warcFile = req.query.file
    const warcFilePath = `${WARC_DIR}/${req.query.file}`
    const pageUrl = req.query.url

    if (typeof req.query.url === 'undefined') {
      console.log(`${warcFilePath} - no page url provided`)
      res.status(404).send('No archive page provided')
      return
    }

    if (!warcFile.startsWith('http') && !fs.existsSync(warcFilePath)) {
      console.log(`${warcFilePath} - archive not found`)
      res.status(404).send('Archive not found')
      return
    }

    res.render('embed', { warcFile, pageUrl })
  })

  replayServer.listen(9990)
}


// No longer needed at the moment; leaving temporarily for documentation
const injectScriptFiles = async (frame) => {
  log(Log.INFO, 'Injecting utility scripts into frame')

  // await frame.addScriptTag({ content: `${log}` })

  // await parent.addScriptTag({ path: `${__dirname}/js/debug.js` })

  // await frame.addStyleTag({ path: `${__dirname}/css/debug.css` })
}


const crawlPage = async () => {
  await initializeBrowser()
  await initializePage(page)

  const _crawlStartTime = performance.now()

  await loadPage()

  const _loadTime = (performance.now() - _crawlStartTime) / 1000
  const _processStartTime = performance.now()

  await savePageMetrics()

  saveNetworkLogs()

  await parseDOM()

  await extractPageElements()

  await saveScreenshots()

  // await extractFullHTML()

  // Record late requests here to record any requests which occured during page processing (should be none)
  if (Object.keys(lateRequests).length) {
    if (!fs.existsSync(`${NET_CACHE}`)) fs.mkdirSync(`${NET_CACHE}`)
    fs.writeFileSync(`${NET_CACHE}/requests_late.jsonl`,
      Object.values(lateRequests).map(r => JSON.stringify(r)).join('\n')
    )
  }

  const _processTime = (performance.now() - _processStartTime) / 1000
  const _crawlTime = (performance.now() - _crawlStartTime) / 1000

  log(Log.INFO, `Page loaded: ${_loadTime.toFixed(2)} seconds`)
  log(Log.INFO, `Page processing complete: ${_processTime.toFixed(2)} seconds`)
  log(Log.INFO, `Crawl complete: ${_crawlTime.toFixed(2)} seconds`)

  if (fs.existsSync(`${CACHE}/error.json`)) {
    try {
      fs.unlinkSync(`${CACHE}/error.json`)
    } catch (error) {
      log(Log.ERROR, 'Unable to clear error file...')
    }
  }
}


/* ---
// Puppeteer configuration functions
--- */
const initializeBrowser = async () => {
  log(Log.INFO, 'Initializing browser')

  // browser = await puppeteer.connect({ browserURL: 'chromium-browser:9222' })

  browser = await puppeteer.launch({
    headless: 'new',
    // headless: false,
    defaultViewport: { width: VIEWPORT[0], height: VIEWPORT[1] },
    devtools: true,
    dumpio: DEBUG ? true : false, // https://github.com/puppeteer/puppeteer/issues/1944#issuecomment-701897009
    // ignoreHTTPSErrors: true,
    // slowMo: 1000,    // 1 second slowmo for debugging
    args: [
      // '--disable-dev-shm-usage',
      '--mute-audio',
      '--hide-scrollbars',
      '--enable-features=NetworkService', // Enable service workers
      '--disable-features=site-per-process',
      '--autoplay-policy=no-user-gesture-required',
      '--disable-web-security',
      '--disable-features=IsolateOrigins',
      '--disable-site-isolation-trials',
      // '--disable-features=BlockInsecurePrivateNetworkRequests',
      // `--disable-extensions-except=${cookieIgnorePath}`,
      // `--load-extension=${cookieIgnorePath}`,
    ]
  })

  // userAgent = await browser.userAgent()
  // userAgent = `${userAgent} - Memento Damage Analyzer (memento-damage.cs.odu.edu), ODU WS-DL (@WebSciDL), David Calano <dcalano@odu.edu>`

  page = (await browser.pages())[0]
}


const initializePage = async () => {
  log(Log.INFO, 'Initializing page')

  await page.exposeFunction('log', log)
  await page.exposeFunction('sleep', sleep)

  page.on('error', e => {
    if (!pageErrors.includes(e)) {
      pageErrors.push(e)
      log(Log.ERROR, 'Page Error:\n' + e)
    }
  })
  page.on('pageerror', e => {
    if (!pageErrors.includes(e)) {
      pageErrors.push(e)
      log(Log.ERROR, `Page PageError:\n${e}`)
    }
  })

  page.setDefaultNavigationTimeout(TIMEOUT)
  page.setDefaultTimeout(TIMEOUT)

  await page.setBypassCSP(true)

  await page.setViewport({ width: VIEWPORT[0], height: VIEWPORT[1] })

  // await page.setUserAgent(userAgent)

  pageSession = await page.target().createCDPSession()
  await pageSession.send('Page.enable')
  await pageSession.send('DOM.enable')
  await pageSession.send('CSS.enable')
  await pageSession.send('Profiler.enable')
  await pageSession.send('ServiceWorker.enable')
  await pageSession.send('Fetch.enable')
  await pageSession.send('Console.enable')

  await pageSession.send('Target.setAutoAttach', {
    autoAttach: true,
    flatten: true,
    waitForDebuggerOnStart: false,
  })

  await pageSession.on('ServiceWorker.workerErrorReported', (error) => {
    log(Log.ERROR, `Service worker error: ${JSON.stringify(error)}`)
  })

  await enablePuppeteerNetworkInterception()
  let pageTargetId = await page.target()._targetId
  await enableCDPNetworkMonitoring(pageSession, pageTargetId)

  pageSession.on('Fetch.requestPaused', async ({requestId, request}) => {
    if (!abortNewRequests) {
      await pageSession.send('Fetch.continueRequest', {requestId})
      return
    }

    lateRequests[request.requestId] = request
    await pageSession.send('Fetch.failRequest', {requestId, 'errorReason': 'TimedOut'})
  })

  pageSession.on('Console.messageAdded', (message) => {
    console.log(JSON.stringify(message))

    if (message.message.url.endsWith('sw.js') && /^(Read) (\d+) (records)$/.test(message.message.text)) {
      warcLoadTimeout = 30
    }
  })

  browser.on('targetcreated', async (target) => {
    console.log(`New target created: ${target.type()}, ID: ${target._targetId}`)
    // console.log(`Monitoring network events for targetId: ${target._targetId}`)
    const targetCDPClient = await target.createCDPSession()

    targetCDPClient.send('Console.enable')
    targetCDPClient.on('Console.messageAdded', (message) => {
      console.log(JSON.stringify(message))

      if (message.message.url.endsWith('sw.js') && /^(Read) (\d+) (records)$/.test(message.message.text)) {
        warcLoadTimeout = 30
      }
    })

    if (target.type() === 'service_worker') {
      await enableCDPNetworkMonitoring(targetCDPClient, target._targetId)

      targetCDPClient.connection().on('sessionattached', async (session) => {
        console.log(`Session attached: ${session.id()}`)
        // await enableCDPNetworkMonitoring(session, target._targetId)
      })
    }
  })

  await startPageMetrics()
}


const enablePuppeteerNetworkInterception = async () => {
  // Logs page console messages and redirections
  await page.setRequestInterception(true)

  page.on('request', request => {
    let parentFrame = request.frame().parentFrame()
    if (request.isNavigationRequest() && parentFrame == null) {
      // console.log(`NAV >>> ${request.url()}`)
    }

    request.continue()
  })

  page.on('response', async (response) => {
    let request = response.request()
    let reqUrl = request.url()
    if (reqUrl.startsWith('data:')) return

    let resUrl = response.url()
    try { resUrl = decodeURI(response.url()) } catch (e) { log(Log.ERROR, `Malformed response URI: ${response.url()}`) }
    const headers = response.headers()
    let status = response.status()

    const redirectChain = response.request().redirectChain()
    if (redirectChain && redirectChain.length > 0) {
      let redirections = redirectChain.map(link => {
        try {
          return decodeURI(link.url())
        } catch (e) {
          log(Log.ERROR, `Malformed redirect URI: ${link.url()}`)
          return link.url()
        }
      })
      redirections.push(resUrl)
      redirectMap[redirections[0]] = {'status': status, 'redirects': redirections}
    }

    let _pageUrl = pageUrl
    if (resUrl.endsWith('/') && !_pageUrl.endsWith('/')) _pageUrl = _pageUrl + '/'

    if (resUrl === _pageUrl) {
      if ([301, 302, 303, 307, 308].includes(status)) {
        log(Log.INFO, `Page redirected >> ${headers.location}`)
        pageUrl = decodeURI(headers.location)
      }
      return
    }
  })

  page.on('console', async (msg) => {
    let msgUrl = msg.location()
    msgUrl = msgUrl['url']
    let msgType = msg.type().toUpperCase()
    let msgLevel = null
    switch (msgType) {
      case 'ERROR':
        msgLevel = Log.ERROR
        break
      case 'WARNING':
        msgLevel = Log.WARN
        break
      case 'LOG':
        msgLevel = Log.INFO
        break
      case 'INFO':
        msgLevel = Log.INFO
        break
      case 'DEBUG':
        msgLevel = Log.DEBUG
        break
      default:
        msgLevel = Log.DEBUG
    }

    let logMsg = msg.text()
    if (msgUrl != null) {
      if (msgUrl.indexOf('data') == 0) {
        logMsg = `${msg.text()} >>> [DATA URI]`
      } else {
        try {
          logMsg = `${msg.text()} >>> ${decodeURI(msgUrl)}`
        } catch (e) {
          logMsg = `${msg.text()} >>> MALFORMED >>> ${msgUrl}`
        }
      }
    } else {
      try {
        logMsg = decodeURI(msgUrl)
      } catch (e) {
        console.log('Log message contains malformed URL')
      }
    }

    // if (DEBUG) console.log(`${msgType}: ${logMsg}`)

    if (msgLevel === Log.ERROR && !pageErrors.includes(logMsg)) {
      log(Log.ERROR, logMsg)
      pageErrors.push(logMsg)
    }
  })
}


const enableCDPNetworkMonitoring = async (client, targetId) => {
  await client.send('Network.enable')

  client.on('Network.loadingFailed', (failedRequest) => {
    if (abortNewRequests) return

    // console.log(`--- ${failedRequest.requestId}`)

    cdpRequestFailures[failedRequest.requestId] = failedRequest
    updatePendingRequests('remove', failedRequest.requestId)
  })

  client.on('Network.requestWillBeSent', (request) => {
    if (abortNewRequests) return

    // console.log(`>>> ${request.requestId}`)

    let reqUrl = request.request.url
    try { reqUrl = decodeURI(request.request.url) } catch (e) { console.log(`Malformed request URI: ${request.request.url}`) }
    // reqUrl = decodeURI(request.url().replace('/%(?![0-9a-fA-F]+)/g', '%25')) -- replace % and % without following hex values

    if (reqUrl === pageUrl || navUrls.includes(reqUrl) || reqUrl.indexOf('chrome-extension') === 0 || reqUrl.indexOf('data') === 0) return

    if (request.loaderId.length === 0) request.loaderId = targetId
    cdpRequests[request.requestId] = request
    updatePendingRequests('add', request.requestId)
  })

  client.on('Network.requestServedFromCache', (requestId) => {
    if (Object.keys(pendingRequests).includes(requestId)) {
      console.log('Pending cache request found')
      updatePendingRequests('remove', requestId, 200)
    }

    // console.log(`Requests ${JSON.stringify(requestId)} served from cache`)
  })

  client.on('Network.responseReceived', (response) => {
    if (abortNewRequests) {
      console.log('abort')
      return
    }

    // console.log(`<<< ${response.response.status} : ${response.response.url}`)

    let reqUrl = cdpRequests[response.requestId]?.request.url
    if (reqUrl == null || reqUrl === pageUrl || navUrls.includes(reqUrl) || reqUrl.indexOf('chrome-extension') === 0 || reqUrl.indexOf('data') === 0) return

    if (response.loaderId.length === 0) response.loaderId = targetId
    cdpResponses[response.requestId] = response

    updatePendingRequests('remove', response.requestId, response.response.status)
  })

  // client.on('Network.dataReceived', (dataInfo) => {
  //   console.log(`${targetId} ${dataInfo.requestId} <<< ${dataInfo.dataLength}`)
  // })
}


const startPageMetrics = async () => {
  // Puppeteer CSS and JavaScript coverage
  await Promise.all([
    page.coverage.startCSSCoverage(),
    page.coverage.startJSCoverage()
  ])

  await pageSession.send('CSS.startRuleUsageTracking')

  // CDP JavaScript coverage
  await pageSession.send('Profiler.startPreciseCoverage', {
    callCount: true,
    detailed: true
  })
}


const savePageMetrics = async () => {
  log(Log.INFO, 'Saving page metrics')

  // Disabled temporarily; traces can be large and can significantly increase page processing time
  // await page.tracing.stop()

  // Puppeteer page JS and CSS coverage data
  const [cssCoverage, jsCoverage] = await Promise.all([
    page.coverage.stopCSSCoverage(),
    page.coverage.stopJSCoverage()
  ])

  const calculateUsedBytes = (type, coverage) =>
    coverage.map(({ url, ranges, text }) => {
      let usedBytes = 0;

      ranges.forEach(range => (usedBytes += range.end - range.start - 1));

      return {
        url,
        type,
        usedBytes,
        totalBytes: text.length
      }
    })

  if (cssCoverage != null && cssCoverage.length > 0) {
    let cssByteMap = calculateUsedBytes('css', cssCoverage)
    writeJsonlData('cssByteMap', cssByteMap.map(item => JSON.stringify(item)))
  }
  if (jsCoverage != null && jsCoverage.length > 0) {
    let jsByteMap = calculateUsedBytes('js', jsCoverage)
    writeJsonlData('jsByteMap', jsByteMap.map(item => JSON.stringify(item)))
  }

  // CDP JavaScript coverage data
  const cssCDPCoverage = await pageSession.send('CSS.stopRuleUsageTracking')
  if (cssCDPCoverage != null && cssCDPCoverage['ruleUsage'].length) {
    if (!fs.existsSync(`${DATA_CACHE}`)) fs.mkdirSync(`${DATA_CACHE}`)
    fs.writeFileSync(`${DATA_CACHE}/css_coverage.json`, JSON.stringify(cssCDPCoverage))
  }

  const jsCDPCoverage = await pageSession.send('Profiler.takePreciseCoverage')
  if (jsCDPCoverage != null && jsCDPCoverage['result'].length) {
    if (!fs.existsSync(`${DATA_CACHE}`)) fs.mkdirSync(`${DATA_CACHE}`)
    fs.writeFileSync(`${DATA_CACHE}/js_coverage.json`, JSON.stringify(jsCDPCoverage))
  }
  await pageSession.send('Profiler.stopPreciseCoverage')

  // Puppeteer page metrics
  let pageMetrics = await page.metrics()
  if (pageMetrics != null) {
    if (!fs.existsSync(`${PAGE_CACHE}`)) fs.mkdirSync(`${PAGE_CACHE}`)
    fs.writeFileSync(`${PAGE_CACHE}/metrics.json`, JSON.stringify(pageMetrics))
  }
}


const updatePendingRequests = (action, requestId, status=null) => {
  if (action === 'add' && !abortNewRequests) {
    pendingRequests[requestId] = requestId
    // console.log(`+++ ${requestId}`)
  } else if (action === 'remove') {
    delete pendingRequests[requestId]

    // if (status != null) {
    //   if (status !== 206) console.log(`${status} --- ${requestId}`)
    // } else { console.log(`--- ${requestId}`) }
  }
}


const loadTracerWARC = async () => {
  log(Log.INFO, 'Loading MementoTracer WARC')

  // Navigate to MementoTracer demo results page to load required service worker
  await page.goto('http://tracerdemo.mementoweb.org/results', {
    waitUntil: 'networkidle2',
    timeout: TIMEOUT
  })
  await page.waitForSelector('table > tbody')

  // Grab WARC replay URL from results table
  let table = await page.$$('table > tbody > tr')
  let clickURL = null
  for (let row of table) {
    clickURL = await row.$$eval('td > a', (items, pageUrl) => {
      if (items[3].innerText === pageUrl) { return items[6].innerText } else { return null }
    }, pageUrl)
    if (clickURL != null) break
  }

  if (clickURL == null) {
    log(Log.ERROR, 'Unable to retrieve replay URL from results table')
    return
  } else { log(Log.INFO, `Replay URL retrieved, redirecting to collection portal: ${clickURL}`) }

  // Redirect to WARC replay collection
  await page.goto(clickURL, {
    waitUntil: 'networkidle2',
    timeout: TIMEOUT
  })

  // Grab replay URL from loaded collection
  await page.waitForFunction(() => document.querySelector('.pageList'))
  let linkHandle = await page.$x(`//a[text()="${pageUrl}"]`)
  let replayURL = await page.evaluate(el => el.getAttribute('href'), linkHandle[0])

  // Redirect to replay URL
  await page.goto(replayURL, {
    waitUntil: 'networkidle2',
    timeout: TIMEOUT,
  })

  await page.evaluate('navigator.serviceWorker.ready')
}


const loadPage = async () => {
  log(Log.INFO, 'Loading page')
  if (WARC_URI) { // WARC URI or local file
    if (WARC_URI.startsWith('http://tracerdemo.mementoweb.org')) {
      await loadTracerWARC()
    } else {
      // https://github.com/puppeteer/examples/blob/master/verify_sw_caching.js
      let warcURL = null
      if (WARC_URI.startsWith('http'))
        warcURL = `${WARC_REPLAY_SRV}/?source=${WARC_URI}#view=pages&url=${pageUrl}`
      else
        warcURL = `${WARC_REPLAY_SRV}/embed?file=${WARC_URI}&url=${pageUrl}`

      log(Log.INFO, `Loading WARC: ${warcURL}`)

      pageUrl = warcURL
      await page.goto(warcURL, {
        waitUntil: 'domcontentloaded',
        timeout: NAVIGATION_TIMEOUT
      })

      await waitForWARCLoad()
    }
  } else { // Web URL
    try {
      await page.goto(pageUrl, {
        waitUntil: 'networkidle2',
        timeout: NAVIGATION_TIMEOUT
      })

      let body = await page.$('body')
      if (body == null) throw Error('NoPageBody')

      await sleep(3000) // Slight artificial pause to help ensure smoother page loads
    } catch (e) {
      console.log(e.message)
      if (e.message === 'NoPageBody') {
        fs.writeFileSync(`${CACHE}/error.json`, JSON.stringify({'error': 'Unable to parse page body'}))
      } else if (e.message.indexOf('net::ERR_CONNECTION_REFUSED') === 0) {
        fs.writeFileSync(`${CACHE}/error.json`, JSON.stringify({'error': 'Network Error: Connection Refused'}))
      } else {
        fs.writeFileSync(`${CACHE}/error.json`, JSON.stringify({'error': e.message}))
      }

      exit(1)
    }
  }

  await waitForPendingRequests()

  if (!fs.existsSync(SCREENSHOT_CACHE)) fs.mkdirSync(SCREENSHOT_CACHE)
  let thumbBase64Str = await page.screenshot({
    format: 'jpg',
    fullPage: false,
    optimizeForSpeed: true,
  })
  sharp(thumbBase64Str)
    .resize(640, 360)
    .toFile(`${SCREENSHOT_CACHE}/thumbnail.jpg`, (err, info) => { if (err) log(Log.ERROR, err) })

  if (replayFrame) {
    let replayFrameHeight = await page.evaluate((replayFrame) => { return Math.max(
      replayFrame.contentDocument.body.height || 0,
      replayFrame.contentDocument.body.scrollHeight || 0,
      replayFrame.contentDocument.body.offsetHeight || 0,
      replayFrame.contentDocument.documentElement.clientHeight || 0,
      replayFrame.contentDocument.documentElement.scrollHeight || 0,
      replayFrame.contentDocument.documentElement.offsetHeight || 0
    )}, replayFrame)

    await page.setViewport({width: VIEWPORT[0], height: replayFrameHeight})
  } else {
    await scrollPage()
  }

  if (Object.keys(pendingRequests).length > 0) {
    if (!fs.existsSync(`${NET_CACHE}`)) fs.mkdirSync(`${NET_CACHE}`)

    let pendingReqJson = Object.keys(pendingRequests).map(reqId => (JSON.stringify({'requestId': reqId})))
    fs.writeFileSync(`${NET_CACHE}/requests_pending.jsonl`, pendingReqJson.join('\n'))

    await waitForPendingRequests()

    if (Object.keys(pendingRequests).length > 0) {
      // Reject any pending requests after timeout has been reached
      fs.writeFileSync(`${NET_CACHE}/requests_timedout.log`, Object.keys(pendingRequests).join('\n'))
      Object.keys(pendingRequests).forEach(reqId => updatePendingRequests('remove', reqId, 408))
    }
  }

  abortNewRequests = true

  return
}


const scrollPage = async () => {
  // https://www.screenshotbin.com/blog/handling-lazy-loaded-webpages-puppeteer
  // https://github.com/puppeteer/puppeteer/issues/305#issuecomment-385145048
  const viewportHeight = VIEWPORT[1]
  let scrollPosition = 0

  let pageHeight = await page.evaluate(() => { return Math.max(
    document.body.height || 0,
    document.body.scrollHeight || 0,
    document.body.offsetHeight || 0,
    document.documentElement.clientHeight || 0,
    document.documentElement.scrollHeight || 0,
    document.documentElement.offsetHeight || 0
  )})

  if (viewportHeight < pageHeight) log(Log.INFO, 'Scrolling page')

  // console.log(`Scrolling | Page Height: ${originalPageHeight}px, Viewport Height: ${viewportHeight}px`)
  while (viewportHeight + scrollPosition < pageHeight) {
    await page.evaluate(viewportHeight => { window.scrollBy(0, viewportHeight) }, viewportHeight)
    await sleep(50)
    scrollPosition += viewportHeight
  }

  await page.evaluate(() => { window.scrollTo(0, 0) })
}


const waitForWARCLoad = async () => {
  console.log('Waiting for archive load')

  let intervalId = 0
  await new Promise((resolve, reject) => {
    intervalId = setInterval(async () => {
      let progressValue = -1
      try {
        let progressBar = await page.evaluateHandle(`document.querySelector('replay-web-page').shadowRoot.querySelector('iframe').contentDocument.querySelector('replay-app-main').shadowRoot.querySelector('wr-coll').shadowRoot.querySelector('wr-loader').shadowRoot.querySelector('#progress')`)
        progressValue = await page.evaluate((progressBar) => progressBar.getAttribute('value'), progressBar)
      } catch (e) { progressValue = -1 }
      let replayFrame = null
      try {
        replayFrame = await page.evaluateHandle(`document.querySelector('replay-web-page').shadowRoot.querySelector('iframe').contentDocument.querySelector('replay-app-main').shadowRoot.querySelector('wr-coll').shadowRoot.querySelector('wr-coll-replay').shadowRoot.querySelector('iframe[name="___wb_replay_top_frame"]')`)
      } catch (e) {}

      if (replayFrame != null) {
        resolve('Archive loaded')
      }

      if (progressValue != -1 && DEBUG) {
        console.log(`WARC loading progress: ${progressValue}`)
      }

      warcLoadTimeout -= 1
      if (warcLoadTimeout <= 0) reject('Archive load timed out')
    }, 1000)
  })
    .then((result) => { log(Log.INFO, result) })
    .catch((error) => { log(Log.ERROR, error); exit(1) })
    .finally(() => { clearInterval(intervalId) })
}


const waitForPendingRequests = async () => {
  // Poll pending request pool every 1 second. If all pending requests are cleared, proceed.
  if (Object.keys(pendingRequests).length > 0) {
    log(Log.DEBUG, `Waiting on ${Object.keys(pendingRequests).length} pending requests...`)

    let timeoutId = 0
    const timer = new Promise((resolve, reject) => { timeoutId = setTimeout(() => { reject('Timeout reached') }, RESOURCE_TIMEOUT) })

    // Object.keys(pendingRequests).forEach(r => { console.log(pendingRequests[r]) })
    let intervalId = 0
    const pollPendingRequests = new Promise((resolve, reject) => {
      intervalId = setInterval(() => {
        if (Object.keys(pendingRequests).length === 0) resolve('All pending requests cleared')
      }, 1000)
    })

    await Promise.race([pollPendingRequests, timer])
      .then((result) => { log(Log.INFO, result) })
      .catch((error) => { log(Log.ERROR, error) })
      .finally(async () => {
        clearInterval(intervalId)
        clearTimeout(timeoutId)
      })
  }
}


/* ---
// Page processing functions
--- */
const extractPageElements = async () => {
  log(Log.INFO, 'Extracting page elements')

  const { cssData, jsData, iframeData, textData, imageData, videoData } = await page.evaluate(() => {
    const getBackgroundColor = () => {
      // https://stackoverflow.com/questions/5623838/rgb-to-hex-and-hex-to-rgb
      const rgb2hex = (orig) => {
          let rgb = orig.replace(/\s/g,'').match(/^rgba?\((\d+),(\d+),(\d+)/i)
          return (rgb && rgb.length === 4) ? "" +
          ("0" + parseInt(rgb[1],10).toString(16)).slice(-2) +
          ("0" + parseInt(rgb[2],10).toString(16)).slice(-2) +
          ("0" + parseInt(rgb[3],10).toString(16)).slice(-2) : orig
      }

      const bgColor = window.getComputedStyle(document.body)['backgroundColor']
      return rgb2hex(bgColor) || 'FFFFFF'
    }

    const getStylesheetData = (frame) => {
      let cssData = []

      const parseStylesheetRules = (stylesheet) => {
        let rulesList = []

        let cssRules = {}
        try { cssRules = stylesheet.cssRules } catch (e) { log(40, `Unable to read stylesheet rules: ${stylesheet.href || '[INTERNAL]'}`) }
        Object.values(cssRules).forEach(rule => {
          if (rule instanceof CSSImportRule) {
            rulesList.push({ 'type': 'import', 'url': rule.href, 'references': 0, 'declarations': 1 })
            rulesList = [...rulesList, ...parseStylesheetRules(rule.styleSheet)]
          } else if (rule instanceof CSSMediaRule) {
            let ruleData = {
              'type': 'media',
              'conditionText': rule.conditionText,
              'declarations': 0
            }

            let mediaRules = {}
            try { mediaRules = rule.cssRules } catch (e) { log(40, `Unable to read media rules: ${stylesheet.href || '[INTERNAL]'}`) }
            Object.values(mediaRules).forEach(mediaRule => {
              if (!('selectors' in ruleData)) ruleData['selectors'] = []
              let selector = mediaRule.selectorText
              ruleData['declarations'] += mediaRule.style.length || 0
              ruleData['selectors'].push(selector)

              let nestedMediaRules = {}
              try { nestedMediaRules = mediaRule.cssRules } catch (e) { log(40, `Unable to read media rules: ${stylesheet.href || '[INTERNAL]'}`) }
              if (Object.values(nestedMediaRules).length) {
                if (!('nestedSelectors' in ruleData)) ruleData['nestedSelectors'] = []
                Object.values(nestedMediaRules).forEach(nestedRule => {
                  if (nestedRule instanceof CSSStyleRule) {
                    ruleData['declarations'] += nestedRule.style.length || 0
                    ruleData['nestedSelectors'].push(nestedRule.selectorText)
                  }
                })
              }

              let matchFound = window.matchMedia(selector)
              ruleData['references'] = matchFound ? 1 : 0
            })

            rulesList.push(ruleData)
          } else if (rule instanceof CSSStyleRule) {
            let ruleData = {
              'type': 'style',
              'selectorText': rule.selectorText,
              'declarations': rule.style.length,
              'references': 0
            }

            let nestedRules = {}
            try { nestedRules = rule.cssRules } catch (e) { log(40, `Unable to read nested rules: ${stylesheet.href || '[INTERNAL]'}`) }
            if (Object.values(nestedRules).length) {
              if (!('nestedSelectors' in ruleData)) ruleData['nestedSelectors'] = []
              Object.values(nestedRules).forEach(nestedRule => {
                if (nestedRule instanceof CSSStyleRule) {
                  ruleData['declarations'] += nestedRule.style.length || 0
                  ruleData['nestedSelectors'].push(nestedRule.selectorText)
                }

                let matches = frame.querySelectorAll(`${rule.selectorText} > ${nestedRule.selectorText}`)
                ruleData['references'] += Object.keys(matches).length || 0
              })
            } else {
              let matches = frame.querySelectorAll(rule.selectorText)
              ruleData['references'] += Object.keys(matches).length || 0
            }

            rulesList.push(ruleData)
          } else if (rule.constructor.name === 'CSSStyleRule') {
            let matches = frame.querySelectorAll(rule.selectorText)
            let ruleData = {
              'type': 'style',
              'selectorText': rule.selectorText,
              'declarations': rule.style.length,
              'references': Object.keys(matches).length || 0
            }
            rulesList.push(ruleData)
          }
        })

        return rulesList
      }

      let stylesheets = frame.styleSheets || {}
      const adoptedStylesheets = frame.adoptedStyleSheets || {}
      stylesheets = [...stylesheets, ...adoptedStylesheets]

      Object.values(stylesheets).forEach(stylesheet => {
        try {
          let cssHtml = stylesheet.ownerNode?.outerHTML || null
          if (cssHtml != null) cssHtml = cssHtml.replace(/[\r\n\s]+/gm, ' ')

          let stylesheetRules = parseStylesheetRules(stylesheet)
          let totalDeclarations = 0, totalReferences = 0
          stylesheetRules.forEach(rule => {
            totalDeclarations += rule['declarations']
            totalReferences += rule['references']
          })

          cssData.push({
            'url' : stylesheet['href'] || '[INTERNAL]',
            'cssHtml' : cssHtml,
            'totalReferences': totalReferences,
            'totalDeclarations': totalDeclarations,
            'rules': stylesheetRules
          })
        } catch (e) { log(40, `Error serializing stylesheet: ${e.message}`) }
      })

      return cssData
    }

    const getJavaScriptData = (node) => {
      let jsData = []
      let scripts = node.querySelectorAll('script')
      Object.values(scripts).forEach(script => {
        let js = { 'url': script['src'] || '[INTERNAL]' }
        if (script.innerHTML) js['code'] = script.innerHTML
        jsData.push(js)
      })

      return jsData
    }

    const getTextData = (node, frameArea) => {
      // TODO: using document as walk root gets text from <head> but using document.body as root doesnt get sk
      let pageText = []

      const findTextNodes = (node, textNodes) => {
        node = node.firstChild
        while (node) {
            if (node.nodeType == Node.TEXT_NODE) textNodes.push(node)
            node = node.nextSibling
        }
      }

      let textNodes = []
      findTextNodes(node, textNodes)
      textNodes.forEach(node => {
        if (node.nodeType == Node.TEXT_NODE) {
          let text = node.nodeValue.trim()
          if (text.length > 0) {
            let parentNode = node.parentNode
            let wrapper = document.createElement('pre')
            parentNode.insertBefore(wrapper, node)
            wrapper.appendChild(node)
            wrapper.dataset._md='unformatted text'
          }
        }
      })

      textNodes = [...node.querySelectorAll('*')]
        .filter(el => el.tagName !== 'HEAD')
        .filter(el => el.tagName !== 'SCRIPT' && el.tagName !== 'STYLE' && el.innerText)

      textNodes.forEach(el => {
        let tag = el.tagName.toLowerCase()
        let text = el.innerText
        let textHtml = el.innerHTML

        let id = el.getAttribute('id')
        let cssClasses = el.getAttribute('class') || el.getAttribute('className')
        if (cssClasses != null) { cssClasses = cssClasses.split(/\s+/).filter(c => c !== '') }
        let elStyle = el.getAttribute('style')
        if (elStyle != null) elStyle = elStyle.replace(/[\r\n\s]+/gm, ' ').trim()

        let { x, y, width, height, top, right, bottom, left } = el.getBoundingClientRect()
        let boundingBox = {
          'left': left, 'right': right, 'top': top, 'bottom': bottom,
          'x': frameArea['x']+x, 'y': frameArea['y']+y, 'width': width, 'height': height
        }

        let textItem = {
          'tag': tag,
          'text': text,
          'textHtml': textHtml,
          'area': boundingBox,
        }

        if (id != null) textItem['id'] = id
        if (cssClasses != null) textItem['classes'] = cssClasses
        if (elStyle != null) textItem['style'] = elStyle
        textItem['visible'] = !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)

        pageText.push(textItem)
      })

      return pageText
    }

    const getImageData = (node, frameArea) => {
      let images = {}

      node.querySelectorAll('img').forEach(el => {
        let src = el['data-original'] || el['data-src'] || el['src'] || null
        if (src == null) return
        let srcKey = src.slice(-150)
        if (src.indexOf('data') == 0) src = '[DATA URI]'

        let id = el.getAttribute('id')
        let cssClasses = el.getAttribute('class') || el.getAttribute('className')
        if (cssClasses != null) { cssClasses = cssClasses.split(/\s+/).filter(c => c !== '') }
        let elStyle = el.getAttribute('style')
        if (elStyle != null) elStyle = elStyle.replace(/[\r\n\s]+/gm, ' ').trim()

        let altText = el.getAttribute("alt") || null

        let { x, y, width, height, top, right, bottom, left } = el.getBoundingClientRect()
        let boundingBox = {
          'left': left, 'right': right, 'top': top, 'bottom': bottom,
          'x': frameArea['x']+x, 'y': frameArea['y']+y, 'width': width, 'height': height
        }

        let parentBoundingBox = null
        let parentSelectors = [], p = el
        let parentEl = el.parentElement || el.parentNode
        if (parentEl) {
          while ((p = p.parentElement || p.parentNode) && p != null && p !== document) {
            if (p.tagName === 'BODY' || p.tagName === 'HTML') break
            try { parentSelectors.push(p.tagName.toLowerCase()) } catch (e) {}
          }

          try {
            ({ x, y, width, height, top, right, bottom, left } = parentEl.getBoundingClientRect())
            parentBoundingBox = {
              'left': left, 'right': right, 'top': top, 'bottom': bottom,
              'x': frameArea['x']+x, 'y': frameArea['y']+y, 'width': width, 'height': height
            }
          } catch (e) { }
        }


        if (!(srcKey in images)) images[srcKey] = {}
        images[srcKey]['url'] = src
        if (!('area' in images[srcKey])) images[srcKey]['area'] = []
        images[srcKey]['area'].push(boundingBox)
        if (parentBoundingBox != null)
          images[srcKey]['parentArea'] = parentBoundingBox
        else
          images[srcKey]['parentArea'] = frameArea
        if (parentSelectors.length)
          images[srcKey]['parents'] = parentSelectors
        else
          images[srcKey]['parents'] = ['body', 'iframe']
        if (id != null) images[srcKey]['id'] = id
        if (altText != null) images[srcKey]['alt'] = altText
        if (elStyle != null) images[srcKey]['style'] = elStyle
        if (cssClasses != null) images[srcKey]['classes'] = cssClasses
        images[srcKey]['visible'] = !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
      })

      return Object.values(images) || []
    }

    const getVideoData = (node, frameArea) => {
      let videos = {}

      node.querySelectorAll('video').forEach(el => {
        let src = el['currentSrc'] || el['src'] || null
        if (src == null) return
        let srcKey = src.slice(-150)
        if (src.indexOf('data') == 0) src = '[DATA URI]'

        let id = el.getAttribute('id')
        let cssClasses = el.getAttribute('class') || el.getAttribute('className')
        if (cssClasses != null) { cssClasses = cssClasses.split(/\s+/).filter(c => c !== '') }
        let elStyle = el.getAttribute('style')
        if (elStyle != null) elStyle = elStyle.replace(/[\r\n\s]+/gm, ' ').trim()

        let altText = el.getAttribute("alt") || null

        let { x, y, width, height, top, right, bottom, left } = el.getBoundingClientRect()
        let boundingBox = {
          'left': left, 'right': right, 'top': top, 'bottom': bottom,
          'x': frameArea['x']+x, 'y': frameArea['y']+y, 'width': width, 'height': height
        }

        let parentBoundingBox = null
        let parentSelectors = [], p = el
        let parentEl = el.parentElement || el.parentNode
        if (parentEl) {
          while ((p = p.parentElement || p.parentNode) && p != null && p !== document) {
            try { parentSelectors.push(p.tagName.toLowerCase()) } catch (e) {}
          }

          try {
            ({ x, y, width, height, top, right, bottom, left } = parentEl.getBoundingClientRect())
            parentBoundingBox = {
              'left': left, 'right': right, 'top': top, 'bottom': bottom,
              'x': frameArea['x']+x, 'y': frameArea['y']+y, 'width': width, 'height': height
            }
          } catch (e) { }
        }

        // let videoError = null
        // if (el.getAttribute('href').includes('web.archive.org/web/')) {
        //   let player = el.closest('.wm-videoplayer').find('#wm-video-error')
        //   let wmPlayer = el.closest('.wm-videoplayer')
        //   if (wmPlayer) {
        //     if (wmPlayer.children('#wm-video-error').length > 0) videoError = 'Wayback Machine has not archived this video'

        //     let noScript = $(wmPlayer).siblings('noscript')
        //     if (noScript) {
        //       // TODO: grabbing html representation of noscript string is MODIFYING the a[href] and removing the wayback prefix?
        //       let nsHtml = $(noScript).html()
        //       let nsAEl = $(nsHtml).find('a')
        //       if (nsAEl) {
        //         let nsSrc = $(nsAEl).attr('href')
        //         if ((src == null) && nsSrc) src = nsSrc
        //       }
        //     }
        //   }
        // }

        if (!(srcKey in videos)) videos[srcKey] = {}
        videos[srcKey]['url'] = src
        if (!('area' in videos[srcKey])) videos[srcKey]['area'] = []
        videos[srcKey]['area'].push(boundingBox)
        if (parentBoundingBox != null)
          videos[srcKey]['parentArea'] = parentBoundingBox
        else
          videos[srcKey]['parentArea'] = frameArea
        if (parentSelectors.length)
          videos[srcKey]['parents'] = parentSelectors
        else
          videos[srcKey]['parents'] = ['body, iframe']
        if (altText != null) videos[srcKey]['alt'] = altText
        if (id != null) videos[srcKey]['id'] = id
        if (cssClasses != null) videos[srcKey]['classes'] = cssClasses
        if (elStyle != null) videos[srcKey]['style'] = elStyle
        videos[srcKey]['visible'] = !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
      })

      return Object.values(videos) || []
    }

    const getIFrameData = (frame, frameArea) => {
      let id = frame.getAttribute('id')
      let cssClasses = frame.getAttribute('class') || frame.getAttribute('className')
      if (cssClasses != null) { cssClasses = cssClasses.split(/\s+/).filter(c => c !== '') }
      let frameStyle = frame.getAttribute('style')
      if (frameStyle != null) frameStyle = frameStyle.replace(/[\r\n\s]+/gm, ' ').trim()

      let { x, y, width, height, top, right, bottom, left } = frame.getBoundingClientRect()
      let boundingBox = {
        'left': left, 'right': right, 'top': top, 'bottom': bottom,
        'x': frameArea['x']+x, 'y': frameArea['y']+y, 'width': width, 'height': height
      }

      const iframe = {}
      iframe['area'] = [boundingBox]
      if (id != null) iframe['id'] = id
      if (cssClasses != null) iframe['classes'] = cssClasses
      if (frameStyle != null) iframe['style'] = frameStyle
      iframe['visible'] = !!(frame.offsetWidth || frame.offsetHeight || frame.getClientRects().length)

      return iframe
    }

    let imageData = []
    let videoData = []
    let iframeData = []
    let textData = []
    let cssData = []
    let jsData = []

    const walk = (node, frameUrl, frameArea) => {
      let bgcolor = getBackgroundColor(node)
      if (bgcolor == '000000') document.body.style.backgroundColor = '#ffffff'

      let frameCSS = getStylesheetData(node).map(s => ({frame: frameUrl, ...s}))
      cssData = [...cssData, ...frameCSS]

      let frameJS = getJavaScriptData(node).map(s => ({frame: frameUrl, ...s}))
      jsData = [...jsData, ...frameJS]

      let frameImages = getImageData(node, frameArea).map(i => ({frame: frameUrl, ...i}))
      imageData = [...imageData, ...frameImages]

      let frameVideos = getVideoData(node, frameArea).map(v => ({frame: frameUrl, ...v}))
      videoData = [...videoData, ...frameVideos]

      let frameText = getTextData(node.body || node, frameArea).map(t => ({frame: frameUrl, ...t}))
      textData = [...textData, ...frameText]

      let shadowEls = [...node.querySelectorAll('*')].filter(el => el.shadowRoot).map(el => el.shadowRoot)
      shadowEls.forEach((shadow, i) => {
        let shadowUrl = `${frameUrl}#shadow-${i}`
        // log(10, `Diving shadowroot: ${shadowUrl}`)
        walk(shadow, shadowUrl, frameArea)
      })

      node.querySelectorAll('iframe').forEach(frameEl => {
        let frame = frameEl.contentDocument
        if (frame == null) return

        let frameUrl = frame.location?.href || null
        if (frameUrl != null && frameUrl !== 'about:blank') {
          let frameDetails = getIFrameData(frameEl, frameArea)
          frameDetails = {'url': frameUrl, ...frameDetails}
          iframeData.push(frameDetails)

          // log(10, `Diving iframe: ${frameUrl}`)
          walk(frame, frameUrl, frameDetails['area'][0])
        }
      })
    }

    let mainFrameDetails = getIFrameData(document.body, {'x': 0, 'y': 0})
    mainFrameDetails = {'url': document.documentURI, ...mainFrameDetails}
    iframeData.push(mainFrameDetails)

    walk(document, document.documentURI, mainFrameDetails['area'][0])

    return { cssData, jsData, iframeData, textData, imageData, videoData }
  }, log)

  writeJsonlData('css', cssData.map(s => JSON.stringify(s)))
  writeJsonlData('js', jsData.map(s => JSON.stringify(s)))
  writeJsonlData('text', textData.map(t => JSON.stringify(t)))
  writeJsonlData('image', imageData.map(i => JSON.stringify(i)))
  writeJsonlData('video', videoData.map(v => JSON.stringify(v)))
  writeJsonlData('iframe', iframeData.map(f => JSON.stringify(f)))
}


const saveScreenshots = async () => {
  log(Log.INFO, 'Generating page screenshot(s)')

  // Related:
  // https://screenshotone.com/blog/a-complete-guide-on-how-to-take-full-page-screenshots-with-puppeteer-playwright-or-selenium/#fixing-the-most-issues-at-once

  if (!fs.existsSync(SCREENSHOT_CACHE)) fs.mkdirSync(SCREENSHOT_CACHE)

  await page.screenshot({
    path: `${SCREENSHOT_CACHE}/screenshot.png`,
    format: 'png',
    fullPage: true,
    optimizeForSpeed: true
  })

  if (replayFrame)
    await page.evaluate((replayFrame) => replayFrame.contentDocument.body.style.background = 'transparent', replayFrame)
  else
    await page.evaluate(() => document.body.style.background = 'transparent')
  await page.screenshot({
    path: `${SCREENSHOT_CACHE}/screenshot_nobg.png`,
    format: 'png',
    fullPage: true,
    omitBackground: true,
    optimizeForSpeed: true
  })
}


const saveNetworkLogs = () => {
  log(Log.INFO, 'Processing network resources')

  if (!fs.existsSync(`${NET_CACHE}`)) fs.mkdirSync(`${NET_CACHE}`)

  if (Object.keys(cdpRequests).length)
    fs.writeFileSync(`${NET_CACHE}/requests.jsonl`, Object.values(cdpRequests).map(item => JSON.stringify(item)).join('\n'))
  if (Object.keys(cdpRequestFailures).length)
    fs.writeFileSync(`${NET_CACHE}/requests_failed.jsonl`, Object.values(cdpRequestFailures).map(item => JSON.stringify(item)).join('\n'))
  if (Object.keys(cdpResponses).length)
    fs.writeFileSync(`${NET_CACHE}/responses.jsonl`, Object.values(cdpResponses).map(item => JSON.stringify(item)).join('\n'))
  if (Object.keys(redirectMap).length)
    fs.writeFileSync(`${NET_CACHE}/redirects.jsonl`, Object.values(redirectMap).map(item => JSON.stringify(item)).join('\n'))
}


const parseDOM = async () => {
  log(Log.INFO, 'Processing HTML and DOM Tree')

  const html = await page.content()
  if (html == null) {
    log(Log.ERROR, 'Unable to retrieve HTML source')
    await shutdown()
  }

  if (!fs.existsSync(`${PAGE_CACHE}`)) fs.mkdirSync(`${PAGE_CACHE}`)
  fs.writeFileSync(`${PAGE_CACHE}/source.html`, html)

  let fullPageSource = await pageSession.send('Page.captureSnapshot')
  if (fullPageSource != null) fs.writeFileSync(`${PAGE_CACHE}/source_full.html`, fullPageSource.data)

  let { pageWidth, pageHeight } = await page.evaluate(() => {
    const html = document.documentElement
    const body = document.body

    let pageWidth = Math.max(
      body.scrollWidth || 0, body.offsetWidth || 0,
      html.clientWidth || 0, html.scrollWidth || 0, html.offsetWidth || 0
    )
    let pageHeight = Math.max(
      body.scrollHeight || 0, body.offsetHeight || 0,
      html.clientHeight || 0, html.scrollHeight || 0, html.offsetHeight || 0
    )

    return { pageWidth, pageHeight }
  })
  log(Log.INFO, `Page dimensions: ${pageWidth} x ${pageHeight}`)

  if (pageWidth === 0 && pageHeight === 0) {
    log(Log.ERROR, 'Unable to load page content')
    await shutdown()
  }
}


const determinePageType = async () => {
  // let pageDomain = pageUrl

  if ([].includes(pageDomain)) {
    if (pageDomain === 'github.com') {
      // document.querySelector('table[aria-labelledby="files-and-folders"]')
    }

    if (pageDomain === 'github.com') {
      // document.querySelector('table[data-testid="file-tree-table"]')
      // document.querySelector('.tree-content-holder > div > table')
    }

    if (pageDomain === 'bitbucket.com') {
      // document.querySelector('table[data-qa="repository-directory"]')
    }

    if (pageDomain === 'sourceforge.net') {
      // document.querySelector('#content_base > div[class^=grid-] > div > table')
    }

    if (pageDomain === 'codeberg.org') {
      // document.querySelector('#repo-files-table')
    }


  } else {
    // Fall back check

    // document.querySelector('table')
    if (table.id && table.id.includes('repo')) {

    } else {
      // if closest() parent has
    }
  }
}


const shutdown = async () => {
  page?.removeAllListeners()
  await browser?.close()
  // if (replayServer != null) replayServer.close(() => { log(Log.INFO, 'Replay server stopped') })
  exit(0)
}


/* ---
// "Engage!" -Jean Luc Picard
--- */
try {
  if (WARC_URI) {
    if (WARC_DIR == null) {
      log(Log.ERROR, 'No WARC directory provided for replay server')
      exit(1)
    }

    // initHTTPServer()
    startReplayServer()
  }

  await crawlPage()
} catch(e) {
  log(Log.ERROR, 'Uncaught error message: ' + e.message)
} finally { await shutdown() }