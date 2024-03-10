import fs from 'fs'
import { dirname } from 'path'
import { fileURLToPath } from 'url'
import express from 'express'

if (process.argv.length !== 4) process.exit(1)
if (! /^[0-9]+$/.test(process.argv.at(2))) { exit(1) }

const replayPort = process.argv.at(2)

const __dirname = dirname(fileURLToPath(import.meta.url))
const warcDir = process.argv.at(3)


const replaySrv = express()
replaySrv.set('view engine', 'ejs')

replaySrv.use(express.static(__dirname))
replaySrv.use(express.static(warcDir))


replaySrv.head('/ping', (req, res) => { res.status(200) })


replaySrv.get('/', (req, res) => {
  fs.createReadStream(`${__dirname}/index.html`, 'utf8').pipe(res)
})


replaySrv.get('/embed', (req, res) => {
  const warcFile = req.query.file
  const warcFilePath = `${warcDir}/${req.query.file}`
  const pageUrl = req.query.url

  console.log(warcFilePath, pageUrl)

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

replaySrv.listen(replayPort, () => {
  console.log(`Replay server started on port ${replayPort}`)
})
