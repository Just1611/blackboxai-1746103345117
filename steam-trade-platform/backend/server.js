require('dotenv').config()
const express = require('express')
const cors = require('cors')
const http = require('http')
const { Server } = require('socket.io')
const session = require('express-session')
const passport = require('passport')
const SteamStrategy = require('passport-steam').Strategy
const mongoose = require('mongoose')
const { User, Skin, TradeOffer, Bot } = require('./models')
const BotManager = require('./botManager')

const app = express()
const server = http.createServer(app)
const io = new Server(server, {
  cors: {
    origin: 'http://localhost:3000',
    methods: ['GET', 'POST'],
    credentials: true
  }
})

app.use(cors({
  origin: 'http://localhost:3000',
  credentials: true
}))

app.use(express.json())
app.use(session({
  secret: process.env.SESSION_SECRET || 'secret',
  resave: false,
  saveUninitialized: true
}))

app.use(passport.initialize())
app.use(passport.session())

mongoose.connect(process.env.MONGODB_URI || 'mongodb+srv://just:<just2012_>@cluster0.capxzpu.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0', {
  useNewUrlParser: true,
  useUnifiedTopology: true
}).then(() => {
  console.log('Connected to MongoDB')
}).catch((err) => {
  console.error('MongoDB connection error:', err)
})

passport.serializeUser((user, done) => {
  done(null, user)
})

passport.deserializeUser(async (obj, done) => {
  try {
    const user = await User.findOne({ steamId: obj.id || obj._json.steamid })
    done(null, user || obj)
  } catch (err) {
    done(err, null)
  }
})

passport.use(new SteamStrategy({
  returnURL: process.env.STEAM_RETURN_URL || 'http://localhost:4000/auth/steam/return',
  realm: process.env.STEAM_REALM || 'http://localhost:4000/',
  apiKey: process.env.STEAM_API_KEY || ''
}, async (identifier, profile, done) => {
  try {
    const steamId = profile.id || profile._json.steamid
    let user = await User.findOne({ steamId })
    if (!user) {
      user = new User({
        steamId,
        personaName: profile.displayName || profile._json.personaname,
        avatar: profile.photos && profile.photos.length > 0 ? profile.photos[0].value : '',
        isAdmin: false
      })
      await user.save()
    }
    profile.identifier = identifier
    done(null, user)
  } catch (err) {
    done(err, null)
  }
}))

app.get('/auth/steam',
  passport.authenticate('steam', { failureRedirect: '/' }),
  (req, res) => {
    // The request will be redirected to Steam for authentication, so this
    // function will not be called.
  })

app.get('/auth/steam/return',
  passport.authenticate('steam', { failureRedirect: '/' }),
  (req, res) => {
    res.redirect('http://localhost:3000/dashboard')
  })

app.get('/api/user', (req, res) => {
  if (req.isAuthenticated()) {
    res.json({ user: req.user })
  } else {
    res.status(401).json({ user: null })
  }
})

// Middleware to check if user is authenticated
function ensureAuthenticated(req, res, next) {
  if (req.isAuthenticated()) {
    return next()
  }
  res.status(401).json({ error: 'Unauthorized' })
}

// Middleware to check if user is admin
function ensureAdmin(req, res, next) {
  if (req.isAuthenticated() && req.user && req.user.isAdmin) {
    return next()
  }
  res.status(403).json({ error: 'Forbidden' })
}

// API routes for skins
app.get('/api/skins', ensureAuthenticated, async (req, res) => {
  const skins = await Skin.find({ owner: req.user._id })
  res.json(skins)
})

app.post('/api/skins', ensureAuthenticated, async (req, res) => {
  const { name, game, imageUrl } = req.body
  const skin = new Skin({
    owner: req.user._id,
    name,
    game,
    imageUrl,
    tradable: true
  })
  await skin.save()
  res.json(skin)
})

// API routes for trade offers
app.get('/api/tradeoffers', ensureAuthenticated, async (req, res) => {
  const offers = await TradeOffer.find({
    $or: [{ fromUser: req.user._id }, { toUser: req.user._id }]
  }).populate('offeredSkins requestedSkins fromUser toUser')
  res.json(offers)
})

app.post('/api/tradeoffers', ensureAuthenticated, async (req, res) => {
  const { toUserId, offeredSkins, requestedSkins } = req.body
  const tradeOffer = new TradeOffer({
    fromUser: req.user._id,
    toUser: toUserId,
    offeredSkins,
    requestedSkins,
    status: 'pending'
  })
  await tradeOffer.save()
  res.json(tradeOffer)
})

app.post('/api/tradeoffers/:id/accept', ensureAuthenticated, async (req, res) => {
  const offer = await TradeOffer.findById(req.params.id)
  if (!offer || offer.toUser.toString() !== req.user._id.toString()) {
    return res.status(403).json({ error: 'Not authorized to accept this offer' })
  }
  offer.status = 'accepted'
  offer.updatedAt = new Date()
  await offer.save()
  // TODO: Trigger bot trade execution here
  res.json(offer)
})

app.post('/api/tradeoffers/:id/reject', ensureAuthenticated, async (req, res) => {
  const offer = await TradeOffer.findById(req.params.id)
  if (!offer || offer.toUser.toString() !== req.user._id.toString()) {
    return res.status(403).json({ error: 'Not authorized to reject this offer' })
  }
  offer.status = 'rejected'
  offer.updatedAt = new Date()
  await offer.save()
  res.json(offer)
})

// API routes for bots (admin only)
app.get('/api/admin/bots', ensureAdmin, async (req, res) => {
  const bots = await Bot.find()
  res.json(bots)
})

app.post('/api/admin/bots', ensureAdmin, async (req, res) => {
  const { steamId, personaName } = req.body
  const bot = new Bot({
    steamId,
    personaName,
    status: 'offline',
    createdAt: new Date()
  })
  await bot.save()
  res.json(bot)
})

app.put('/api/admin/bots/:id', ensureAdmin, async (req, res) => {
  const bot = await Bot.findById(req.params.id)
  if (!bot) {
    return res.status(404).json({ error: 'Bot not found' })
  }
  Object.assign(bot, req.body)
  await bot.save()
  res.json(bot)
})

app.delete('/api/admin/bots/:id', ensureAdmin, async (req, res) => {
  await Bot.findByIdAndDelete(req.params.id)
  res.json({ success: true })
})

// API route for admin user management (list users)
app.get('/api/admin/users', ensureAdmin, async (req, res) => {
  const users = await User.find()
  res.json(users)
})

const botManagers = new Map()

async function initializeBots() {
  const bots = await Bot.find()
  bots.forEach(bot => {
    const botManager = new BotManager({
      accountName: bot.steamId,
      password: bot.password, // You need to store encrypted password or use environment variables
      twoFactorCode: bot.twoFactorCode,
      personaName: bot.personaName
    })
    botManager.login()
    botManagers.set(bot._id.toString(), botManager)
  })
}

initializeBots().catch(console.error)

io.on('connection', (socket) => {
  console.log('a user connected')
  socket.on('disconnect', () => {
    console.log('user disconnected')
  })
})

const PORT = process.env.PORT || 4000
server.listen(PORT, () => {
  console.log(`Server listening on port ${PORT}`)
})
