const SteamUser = require('steam-user');
const TradeOfferManager = require('steam-tradeoffer-manager');
const SteamCommunity = require('steamcommunity');
const EventEmitter = require('events');

class BotManager extends EventEmitter {
  constructor(botConfig) {
    super();
    this.client = new SteamUser();
    this.community = new SteamCommunity();
    this.manager = new TradeOfferManager({
      steam: this.client,
      community: this.community,
      language: 'en'
    });
    this.botConfig = botConfig;
    this.loggedIn = false;
    this.setupListeners();
  }

  setupListeners() {
    this.client.on('loggedOn', () => {
      this.loggedIn = true;
      console.log(`Bot ${this.botConfig.personaName} logged on.`);
      this.client.setPersona(SteamUser.EPersonaState.Online);
      this.emit('online');
    });

    this.client.on('webSession', (sessionID, cookies) => {
      this.manager.setCookies(cookies, (err) => {
        if (err) {
          console.error(`Failed to set cookies for bot ${this.botConfig.personaName}:`, err);
          return;
        }
        console.log(`TradeOfferManager ready for bot ${this.botConfig.personaName}`);
        this.emit('ready');
      });
    });

    this.manager.on('newOffer', (offer) => {
      console.log(`New trade offer received by bot ${this.botConfig.personaName} from ${offer.partner.getSteamID64()}`);
      // Automatically accept offers from trusted users or implement your logic here
      // For now, reject all offers to prevent unauthorized trades
      offer.decline((err) => {
        if (err) {
          console.error(`Failed to decline offer: ${err}`);
        } else {
          console.log(`Offer declined by bot ${this.botConfig.personaName}`);
        }
      });
    });

    this.client.on('error', (err) => {
      console.error(`Steam client error for bot ${this.botConfig.personaName}:`, err);
    });

    this.client.on('disconnected', (eresult, msg) => {
      this.loggedIn = false;
      console.log(`Bot ${this.botConfig.personaName} disconnected: ${msg} (${eresult})`);
      // Optionally implement reconnect logic here
    });
  }

  login() {
    this.client.logOn({
      accountName: this.botConfig.accountName,
      password: this.botConfig.password,
      twoFactorCode: this.botConfig.twoFactorCode // if applicable
    });
  }

  logout() {
    this.client.logOff();
  }

  // Implement trade execution logic here
  async executeTrade(offerId) {
    // Placeholder for trade execution logic
  }
}

module.exports = BotManager;
