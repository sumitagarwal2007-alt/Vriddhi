import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
import joblib
import sys

DB_NAME = 'trading_agent.db'

def get_data():
    conn = sqlite3.connect(DB_NAME)
    tf = pd.read_sql_query("SELECT * FROM trade_feedback", conn)
    tx = pd.read_sql_query("SELECT * FROM transactions WHERE action='BUY' ORDER BY timestamp ASC", conn)
    conn.close()
    
    if tf.empty:
        print("No trade feedback data found.")
        sys.exit(1)
        
    tf['timestamp'] = pd.to_datetime(tf['timestamp'], format='ISO8601', errors='coerce', utc=True)
    tx['timestamp'] = pd.to_datetime(tx['timestamp'], format='ISO8601', errors='coerce', utc=True)
    
    buy_hours = []
    
    for _, row in tf.iterrows():
        ticker = row['ticker']
        sell_time = row['timestamp']
        
        past_buys = tx[(tx['ticker'] == ticker) & (tx['timestamp'] <= sell_time)]
        if not past_buys.empty:
            buy_time = past_buys.iloc[-1]['timestamp']
            buy_hour = buy_time.hour + buy_time.minute / 60.0
        else:
            buy_hour = 9.5
            
        buy_hours.append(buy_hour)
        
    tf['buy_hour'] = buy_hours
    return tf

def train_and_save_model():
    print("[*] Loading training data...")
    df = get_data()
    
    # Target
    df['is_win'] = (df['pnl_pct'] > 0).astype(int)
    
    df = df.dropna(subset=['headline', 'reasoning', 'significance_score', 'buy_price'])
    
    df['text_data'] = df['headline'].astype(str) + " " + df['reasoning'].astype(str)
    
    # TF-IDF
    print("[*] Fitting TF-IDF Vectorizer...")
    vectorizer = TfidfVectorizer(stop_words='english', max_features=50, ngram_range=(1, 2))
    text_features = vectorizer.fit_transform(df['text_data']).toarray()
    
    # Numerical Features Available at BUY time
    X_num = df[['significance_score', 'buy_price', 'buy_hour']].values
    
    X = np.hstack([X_num, text_features])
    y = df['is_win'].values
    
    if len(np.unique(y)) < 2:
        print("Not enough variance to train model.")
        sys.exit(0)
    
    # Train
    print("[*] Training Random Forest Classifier...")
    rf = RandomForestClassifier(n_estimators=200, random_state=42, max_depth=10)
    rf.fit(X, y)
    
    # Save Model
    joblib.dump(rf, 'model.pkl')
    joblib.dump(vectorizer, 'vectorizer.pkl')
    print("[+] Model and Vectorizer successfully saved to disk as model.pkl and vectorizer.pkl.")
    print(f"[+] Model Accuracy on Training Data: {rf.score(X, y)*100:.1f}%")

if __name__ == "__main__":
    train_and_save_model()
