import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
import sys

DB_NAME = 'trading_agent.db'

def get_data():
    conn = sqlite3.connect(DB_NAME)
    
    # Get trade feedback
    tf = pd.read_sql_query("SELECT * FROM trade_feedback", conn)
    
    # Get transactions to find entry times
    tx = pd.read_sql_query("SELECT * FROM transactions WHERE action='BUY' ORDER BY timestamp ASC", conn)
    conn.close()
    
    if tf.empty:
        print("No trade feedback data found.")
        sys.exit(1)
        
    # Process timestamps
    tf['timestamp'] = pd.to_datetime(tf['timestamp'], format='ISO8601', errors='coerce', utc=True)
    tx['timestamp'] = pd.to_datetime(tx['timestamp'], format='ISO8601', errors='coerce', utc=True)
    
    # Match entry times to calculate holding duration
    holding_hours = []
    buy_hours = []
    
    for _, row in tf.iterrows():
        ticker = row['ticker']
        sell_time = row['timestamp']
        
        # Find the most recent buy before this sell
        past_buys = tx[(tx['ticker'] == ticker) & (tx['timestamp'] <= sell_time)]
        if not past_buys.empty:
            buy_time = past_buys.iloc[-1]['timestamp']
            duration = (sell_time - buy_time).total_seconds() / 3600.0
            buy_hour = buy_time.hour + buy_time.minute / 60.0
        else:
            duration = 0.0
            buy_hour = 9.5 # default to market open
            
        holding_hours.append(duration)
        buy_hours.append(buy_hour)
        
    tf['holding_hours'] = holding_hours
    tf['buy_hour'] = buy_hours
    
    return tf

def run_analysis():
    print("="*60)
    print(" 🤖 VRIDDHI QUANT: MACHINE LEARNING DEEP ANALYSIS ")
    print("="*60)
    
    df = get_data()
    
    # Define Target: 1 if win, 0 if loss
    df['is_win'] = (df['pnl_pct'] > 0).astype(int)
    
    # Basic Stats
    win_rate = df['is_win'].mean() * 100
    print(f"Total Completed Trades: {len(df)}")
    print(f"Overall Win Rate:       {win_rate:.1f}%\n")
    
    # Filter valid rows
    df = df.dropna(subset=['headline', 'reasoning', 'significance_score', 'buy_price'])
    
    # Combine text for NLP
    df['text_data'] = df['headline'].astype(str) + " " + df['reasoning'].astype(str)
    
    # TF-IDF Vectorization
    print("[*] Vectorizing Text Data (TF-IDF)...")
    vectorizer = TfidfVectorizer(stop_words='english', max_features=50, ngram_range=(1, 2))
    text_features = vectorizer.fit_transform(df['text_data']).toarray()
    text_feature_names = vectorizer.get_feature_names_out()
    
    # Numerical Features
    X_num = df[['significance_score', 'buy_price', 'holding_hours', 'buy_hour']].values
    num_feature_names = ['Significance Score', 'Buy Price', 'Holding Duration (Hrs)', 'Time of Day (Hour)']
    
    # Combine Features
    X = np.hstack([X_num, text_features])
    all_feature_names = num_feature_names + list(text_feature_names)
    y = df['is_win'].values
    
    if len(np.unique(y)) < 2:
        print("Not enough variance in win/loss to train ML model.")
        sys.exit(0)
    
    # Train Random Forest
    print("[*] Training Random Forest Classifier...")
    rf = RandomForestClassifier(n_estimators=200, random_state=42, max_depth=10)
    rf.fit(X, y)
    
    # Extract Feature Importances
    importances = rf.feature_importances_
    
    # Pair with names and sort
    feature_importance_df = pd.DataFrame({
        'Feature': all_feature_names,
        'Importance': importances
    }).sort_values(by='Importance', ascending=False)
    
    print("\n" + "="*40)
    print(" 🎯 TOP PREDICTIVE FEATURES")
    print("="*40)
    print("These variables drive the model's prediction of a Win vs Loss:")
    for i, row in feature_importance_df.head(10).iterrows():
        print(f"{row['Feature']:<25}: {row['Importance']:.4f}")
        
    print("\n" + "="*40)
    print(" 📉 TOXIC KEYWORDS (Correlated with Losses)")
    print("="*40)
    
    # Find text features highly correlated with losses
    toxic_words = []
    for word in text_feature_names:
        word_idx = all_feature_names.index(word)
        # Check mean occurrence of word in winning trades vs losing trades
        win_mean = X[y == 1, word_idx].mean()
        loss_mean = X[y == 0, word_idx].mean()
        
        if loss_mean > win_mean and loss_mean > 0.01:
            ratio = loss_mean / (win_mean + 0.0001)
            toxic_words.append((word, ratio, loss_mean))
            
    toxic_words.sort(key=lambda x: x[1], reverse=True)
    for word, ratio, loss_mean in toxic_words[:10]:
        print(f"Keyword: '{word}' -> {ratio:.1f}x more likely to appear in losing trades")
        
    print("\n" + "="*40)
    print(" 📈 WINNING KEYWORDS (Correlated with Wins)")
    print("="*40)
    
    win_words = []
    for word in text_feature_names:
        word_idx = all_feature_names.index(word)
        win_mean = X[y == 1, word_idx].mean()
        loss_mean = X[y == 0, word_idx].mean()
        
        if win_mean > loss_mean and win_mean > 0.01:
            ratio = win_mean / (loss_mean + 0.0001)
            win_words.append((word, ratio, win_mean))
            
    win_words.sort(key=lambda x: x[1], reverse=True)
    for word, ratio, win_mean in win_words[:5]:
        print(f"Keyword: '{word}' -> {ratio:.1f}x more likely to appear in winning trades")

    print("\n" + "="*40)
    print(" ⏱️ TIME & HOLDING ANALYSIS")
    print("="*40)
    
    # Holding Duration
    win_hold = df[df['is_win']==1]['holding_hours'].mean()
    loss_hold = df[df['is_win']==0]['holding_hours'].mean()
    print(f"Avg Holding Time (Wins):   {win_hold:.2f} hours")
    print(f"Avg Holding Time (Losses): {loss_hold:.2f} hours")
    
    # Time of Day
    win_hour = df[df['is_win']==1]['buy_hour'].mean()
    loss_hour = df[df['is_win']==0]['buy_hour'].mean()
    print(f"\nAvg Entry Time (Wins):   {int(win_hour)}:{int((win_hour%1)*60):02d} EST")
    print(f"Avg Entry Time (Losses): {int(loss_hour)}:{int((loss_hour%1)*60):02d} EST")

if __name__ == "__main__":
    run_analysis()
