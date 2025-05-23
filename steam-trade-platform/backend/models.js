const mongoose = require('mongoose');

const UserSchema = new mongoose.Schema({
  steamId: { type: String, unique: true, required: true },
  personaName: String,
  avatar: String,
  isAdmin: { type: Boolean, default: false },
  createdAt: { type: Date, default: Date.now }
});

const SkinSchema = new mongoose.Schema({
  owner: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  name: String,
  game: String,
  imageUrl: String,
  tradable: { type: Boolean, default: true },
  createdAt: { type: Date, default: Date.now }
});

const TradeOfferSchema = new mongoose.Schema({
  fromUser: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  toUser: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  offeredSkins: [{ type: mongoose.Schema.Types.ObjectId, ref: 'Skin' }],
  requestedSkins: [{ type: mongoose.Schema.Types.ObjectId, ref: 'Skin' }],
  status: { type: String, enum: ['pending', 'accepted', 'rejected', 'cancelled'], default: 'pending' },
  createdAt: { type: Date, default: Date.now },
  updatedAt: Date
});

const BotSchema = new mongoose.Schema({
  steamId: { type: String, unique: true, required: true },
  personaName: String,
  password: { type: String, required: true }, // Store encrypted password
  twoFactorCode: { type: String }, // Optional 2FA code
  status: { type: String, enum: ['online', 'offline', 'busy'], default: 'offline' },
  lastActive: Date,
  createdAt: { type: Date, default: Date.now }
});

module.exports = {
  User: mongoose.model('User', UserSchema),
  Skin: mongoose.model('Skin', SkinSchema),
  TradeOffer: mongoose.model('TradeOffer', TradeOfferSchema),
  Bot: mongoose.model('Bot', BotSchema)
};
