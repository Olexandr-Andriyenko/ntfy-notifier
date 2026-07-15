from pathlib import Path
import json
import yfinance as yf
import requests
from dotenv import load_dotenv
import os

PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = PROJECT_DIR / "config.json"
HISTORY_FILE = PROJECT_DIR / "battle_history.csv"
ENV_FILE = PROJECT_DIR / ".env"
load_dotenv(ENV_FILE)

def load_config(path: Path) -> dict:
    """Lädt und überprüft die config.json"""
    
    if not path.exists():
        raise FileNotFoundError(f"Die Konfiguratinsdatei wurde nicht gefunden: {path}")
    
    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)
    
    players = config.get("players", [])
    
    if len(players) < 2:
        raise ValueError("Für ein Battle müssen mindestens zwei Personen in 'config.json' stehen.")
    
    for player in players:
        if not player.get("name") or not player.get("ticker"):
            raise ValueError("Jeder Eintrag unter 'players' benötigt 'name' und 'ticker'.")
    
    return config

def print_players(players: list[dict]) ->None:
    """Gibt alle Teilnehmer und deren Aktien aus"""
    
    print("\nTeilnehmer des Aktien-Battles:")
    print(15 * "-")
    
    for player in players:
        name = player["name"]
        ticker = player["ticker"]
        print(f"{name}: {ticker}")

def load_stock_data(ticker: str):
    """Lädt die historischen Tageskurse einer Aktie."""
    
    ticker = ticker.upper()
    stock = yf.Ticker(ticker)
    data = stock.history(period="1mo", interval="1d")
    
    if data.empty:
        raise ValueError(f"Für den Ticker '{ticker}' wurden keine Kursdaten gefunden.")
    
    return data

def calculate_change(stock_data) -> tuple[float, float, float]:
    """Berechnet die Veränderung zwischen den letzten beiden Schlusskursen"""
    
    closing_price = stock_data["Close"].dropna()
    
    if len(closing_price) < 2:
        raise ValueError("Es sind nicht genügend Schlusskurse für die Berechnung vorhanden")
    
    previous_price = float(closing_price.iloc[-2])
    current_price = float(closing_price.iloc[-1])
    
    change_percent = (
        (current_price - previous_price) / previous_price * 100
    )
    
    return previous_price, current_price, change_percent

def create_battle_result(player: dict):
    """Erstellt das Aktienergebniss für eine Person"""
    
    name = player["name"]
    ticker = player["ticker"]
    stock_data = load_stock_data(ticker)
    
    previous_price, current_price, change_percent = calculate_change(stock_data)
    market_date = stock_data.index[-1].strftime("%d.%m.%Y")
    
    result = {
        "player": name,
        "ticker": ticker,
        "previous_price": previous_price,
        "current_price": current_price,
        "change_percent": change_percent,
        "market_date": market_date
    }
    
    return result

def get_change_percent(result: dict) -> float:
    """Gibt die prozentuale Veränderung eines Ergebnisses zurück."""
    return result["change_percent"]

def send_winner_notification(winner: dict, ntfy_config: dict) -> tuple[bool, str]:
    """Sendet den Gewinner als Push Nachricht über ntfy."""
    
    enabled = ntfy_config.get("enabled", False)
    if not enabled:
        return False, "ntfy ist in der config.json deaktiviert."
    
    server = os.getenv("NTFY_SERVER", "")
    topic = os.getenv("NTFY_TOPIC", "")
    
    if not server or not topic:
        return(
            False,
            "In der .env-Datei müssen 'server' und"
            "'topic' eingetragen sein"
            )
    
    message = (
        f"Gewinner: {winner['player']}\n"
        f"Aktie: {winner['ticker']}\n"
        f"Aktueller Kurs: {winner['current_price']:.2f}\n"
        f"Veränderung: {winner['change_percent']:.2f} %\n"
        f"Marktstand: {winner['market_date']}"
    )
    
    try:
        response = requests.post(
            f"{server}/{topic}",
            data=message.encode("utf-8"),
            headers={
                "Title": "Aktien-Battle: Gewinner",
                "Priority": "default",
                "Tags": "trophy,chart_with_upwards_trend"
            },
            timeout=10
        )
        
        response.raise_for_status()
        
        return True, "Push Nachricht wurde erfolgreich gesendet"
        
    except requests.RequestException as error:
        return False, f"Push Nachricht konnte nicht gesendet werden: {error}"

def run_battle(players: list[dict]):
    """Führt das Aktien Battle für alle Spieler durch."""
    
    results = []
    errors = []
    
    for player in players:
        try:
            result = create_battle_result(player)
            results.append(result)#
        except Exception as error:
            error_message = (
                f"{player['name'] ({player['ticker']}): {error}}"
            )
            errors.append(error_message)
    
    results.sort(key=get_change_percent, reverse=True)
    return results, errors

if __name__ == "__main__":
    config = load_config(CONFIG_FILE)
    players = config["players"]
    ntfy_config = config.get("ntfy", {})
    
    print_players(players)
    
    results = []
    
    for player in players:
        print(f"\nLade Kursdaten für {player['name']} ({player['ticker']})...")
        result = create_battle_result(player)
        results.append(result)
    
    results.sort(key=get_change_percent, reverse=True)
    
    print("\nRangliste:")
    print(30 * "-")
    
    
    rank = 1
    for result in results:
        print(
            f"{rank}. {result['player']} | "
            f"{result['ticker']} | "
            f"Kurs: {result['current_price']:.2f} | "
            f"Veränderung: {result['change_percent']:.2f} %"
        )
        rank += 1
    
    winner = results[0]
    
    print(30 * "-")
    print(f"Der Gewinner ist {winner['player']}!")
    
    success, notification_message =  send_winner_notification(winner, ntfy_config)
    print(notification_message)