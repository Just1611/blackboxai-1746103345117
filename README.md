
Built by https://www.blackbox.ai

---

# CS2 SKINS

## Project Overview
CS2 SKINS is a web application designed for trading and opening CS:GO skins efficiently. The platform offers users the ability to manage their inventory, trade skins with bots, and open cases with exciting chances of winning rare skins. It provides real-time updates, automated features, and a secure authentication method via Steam.

## Installation
To set up the CS2 SKINS application locally, follow these steps:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/cs2-skins.git
   cd cs2-skins
   ```

2. **Set up a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install dependencies:**
   Make sure you have `Flask` and other required packages in your environment:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables:**
   Create a `.env` file in the root of the project to store your environment variables:
   ```plaintext
   STEAM_API_KEY=your_steam_api_key_here
   FLASK_SECRET_KEY=your_secret_key_here
   JWT_SECRET=your_jwt_secret_here
   ```

5. **Start the Flask server:**
   ```bash
   python server.py
   ```

6. **Access the application:**
   Open your web browser and go to `http://localhost:8000`.

## Usage
After starting the application, users can:

- **Login with Steam:** Use the Steam login button to authenticate and manage your inventory.
- **Trade Skins:** Navigate to the trading interface to trade skins with bot entities.
- **Open Cases:** Attempt to open virtual cases for a chance to obtain random skins.
- **Manage Wallet:** View and manage your wallet, including deposits and withdrawals.

## Features
- **Instant Trading:** Automated bot trading available 24/7.
- **Secure Platform:** Usage of Steam authentication for safe interactions.
- **Case Openings:** Open exciting cases with a chance to win high-tier skins.
- **User Dashboard:** View trading history and recent transactions.
- **Real-time Updates:** See live drops on the platform.

## Dependencies
The following dependencies are necessary for this project, as defined in the `requirements.txt` file:
- Flask: A lightweight WSGI web application framework.
- Flask-Cors: A Flask extension that allows you to handle Cross-Origin Resource Sharing.
- Flask-Sock: Provides WebSocket support for Flask.
- Requests: A simple HTTP library for Python.
- Bcrypt: A library to help hash passwords securely.
- Python-dotenv: Reads key-value pairs from a `.env` file and adds them to environment variables.
- Werkzeug: A comprehensive WSGI web application library.

## Project Structure
Here’s a brief overview of the project structure:

```
cs2-skins/
│
├── index.html               # Landing page of the application.
├── login.html               # Login page for user authentication.
├── dashboard.html           # User dashboard showing user statistics and activities.
├── trade.html               # Trading interface for managing skins.
├── wallet.html              # User wallet for managing funds and transactions.
├── boxes.html               # Case opening interface.
│
├── server.py                # Flask server application handling endpoints and business logic.
├── steam_auth.py            # Module handling Steam authentication procedures.
│
├── requirements.txt         # List of Python dependencies for the project.
└── .env                     # Environment variables configuration file.
```

## Conclusion
CS2 SKINS provides an engaging platform for trading and managing CS:GO skins securely and efficiently. For any issues or improvements, feel free to open an issue or contribute to the project!