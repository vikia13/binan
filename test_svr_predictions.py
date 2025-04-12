import os
import logging
import argparse
import sqlite3
import pandas as pd
from svr_model import SVRModel
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("svr_testing.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("SVRTesting")

# Load environment variables
load_dotenv()

def evaluate_predictions(db_path, symbol, days_back=7):
    """Evaluate SVR predictions for a symbol over the past days"""
    # Initialize SVR model
    svr_model = SVRModel(db_path=db_path)

    # Get historical price data
    conn = sqlite3.connect(os.path.join(db_path, 'market_data.db'))

    # Calculate timestamp for days_back days ago
    start_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)

    query = '''
    SELECT price, timestamp FROM market_data
    WHERE symbol = ? AND timestamp >= ?
    ORDER BY timestamp
    '''

    df = pd.read_sql_query(query, conn, params=(symbol, start_time))
    conn.close()

    if df.empty:
        logger.info(f"No price data found for {symbol} in the past {days_back} days")
        return None

    # Sample data at regular intervals (every 4 hours)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('datetime')
    df = df.resample('4H').first().dropna()

    # Reset index for easier processing
    df = df.reset_index()

    # Make predictions and evaluate
    results = []

    for i in range(len(df) - 3):  # Skip last 3 points to allow for 12-hour evaluation
        # Get current price data
        current_time = df.iloc[i]['timestamp']
        current_price = df.iloc[i]['price']

        # Make prediction
        prediction_type, confidence = svr_model.predict(symbol)

        # Get actual price 12 hours later (3 points ahead)
        future_price = df.iloc[i + 3]['price']
        actual_change_pct = ((future_price - current_price) / current_price) * 100

        # Determine actual outcome
        threshold = 3.0
        if actual_change_pct > threshold:
            actual_outcome = "LONG"
        elif actual_change_pct < -threshold:
            actual_outcome = "SHORT"
        else:
            actual_outcome = "NEUTRAL"

        # Calculate accuracy
        accuracy = 1.0 if prediction_type == actual_outcome else 0.0

        # Store result
        results.append({
            'timestamp': current_time,
            'datetime': df.iloc[i]['datetime'],
            'current_price': current_price,
            'future_price': future_price,
            'prediction': prediction_type,
            'confidence': confidence,
            'actual_change_pct': actual_change_pct,
            'actual_outcome': actual_outcome,
            'accuracy': accuracy
        })

    # Convert to DataFrame for analysis
    results_df = pd.DataFrame(results)

    # Calculate overall accuracy
    overall_accuracy = results_df['accuracy'].mean() * 100

    # Calculate accuracy by prediction type
    accuracy_by_type = results_df.groupby('prediction')['accuracy'].mean() * 100

    # Calculate accuracy by confidence level
    results_df['confidence_level'] = pd.cut(
        results_df['confidence'],
        bins=[0, 0.6, 0.8, 1.0],
        labels=['Low (<60%)', 'Medium (60-80%)', 'High (>80%)']
    )
    accuracy_by_confidence = results_df.groupby('confidence_level')['accuracy'].mean() * 100

    # Print results
    logger.info(f"SVR Prediction Evaluation for {symbol} (past {days_back} days)")
    logger.info(f"Overall Accuracy: {overall_accuracy:.2f}%")
    logger.info(f"Total Predictions: {len(results_df)}")
    logger.info("\nAccuracy by Prediction Type:")
    for pred_type, acc in accuracy_by_type.items():
        count = len(results_df[results_df['prediction'] == pred_type])
        logger.info(f"- {pred_type}: {acc:.2f}% ({count} predictions)")

    logger.info("\nAccuracy by Confidence Level:")
    for conf_level, acc in accuracy_by_confidence.items():
        count = len(results_df[results_df['confidence_level'] == conf_level])
        logger.info(f"- {conf_level}: {acc:.2f}% ({count} predictions)")

    return results_df

def main():
    parser = argparse.ArgumentParser(description='Test SVR model predictions')
    parser.add_argument('--symbol', type=str, default='BTCUSDT', help='Symbol to evaluate')
    parser.add_argument('--days', type=int, default=7, help='Number of days to look back')
    parser.add_argument('--db_path', type=str, default='data', help='Path to database directory')

    args = parser.parse_args()

    results = evaluate_predictions(args.db_path, args.symbol, args.days)

    if results is not None:
        # Save results to CSV
        output_file = f"{args.symbol}_svr_evaluation.csv"
        results.to_csv(output_file, index=False)
        logger.info(f"Results saved to {output_file}")

if __name__ == "__main__":
    main()
