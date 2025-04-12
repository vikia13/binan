import sqlite3
import pandas as pd
import numpy as np
import os
import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class PerformanceEvaluator:
    def __init__(self, db_path='data'):
        self.db_path = db_path
        self.reports_dir = os.path.join(db_path, 'reports')
        os.makedirs(self.reports_dir, exist_ok=True)
        
        logger.info("Performance evaluator initialized")
    
    def evaluate_predictions(self, days_back=7):
        """Evaluate prediction accuracy for the specified time period"""
        conn = sqlite3.connect(os.path.join(self.db_path, 'ai_model.db'))
        
        # Calculate timestamp for days_back days ago
        start_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)
        
        # Get all predictions in the time period
        query = '''
        SELECT mp.id, mp.symbol, mp.prediction_type, mp.confidence_score, 
               mp.timestamp, mp.features_id, mf.price_change_1h
        FROM model_predictions mp
        JOIN model_features mf ON mp.features_id = mf.id
        WHERE mp.timestamp >= ?
        ORDER BY mp.symbol, mp.timestamp
        '''
        
        df = pd.read_sql_query(query, conn, params=(start_time,))
        
        if df.empty:
            conn.close()
            logger.info("No predictions found for evaluation")
            return None
        
        # Get market data for actual outcomes
        market_conn = sqlite3.connect(os.path.join(self.db_path, 'market_data.db'))
        
        results = []
        
        # Process each prediction
        for _, row in df.iterrows():
            prediction_id = row['id']
            symbol = row['symbol']
            prediction_type = row['prediction_type']
            timestamp = row['timestamp']
            
            # Get price at prediction time
            query = '''
            SELECT price FROM market_data
            WHERE symbol = ? AND timestamp <= ?
            ORDER BY timestamp DESC LIMIT 1
            '''
            
            entry_df = pd.read_sql_query(query, market_conn, params=(symbol, timestamp))
            
            if entry_df.empty:
                continue
                
            entry_price = entry_df['price'].iloc[0]
            
            # Get price 1 hour after prediction
            future_timestamp = timestamp + (3600 * 1000)  # 1 hour in milliseconds
            
            query = '''
            SELECT price FROM market_data
            WHERE symbol = ? AND timestamp >= ?
            ORDER BY timestamp ASC LIMIT 1
            '''
            
            exit_df = pd.read_sql_query(query, market_conn, params=(symbol, future_timestamp))
            
            if exit_df.empty:
                continue
                
            exit_price = exit_df['price'].iloc[0]
            
            # Calculate actual price change
            price_change_pct = ((exit_price - entry_price) / entry_price) * 100
            
            # Determine actual outcome
            threshold = 3.0  # Configurable
            
            if price_change_pct > threshold:
                actual_outcome = "LONG"
            elif price_change_pct < -threshold:
                actual_outcome = "SHORT"
            else:
                actual_outcome = "NEUTRAL"
            
            # Calculate accuracy (1 if prediction matches outcome, 0 otherwise)
            accuracy = 1.0 if prediction_type == actual_outcome else 0.0
            
            # Update prediction with actual outcome
            update_query = '''
            UPDATE model_predictions
            SET actual_outcome = ?, accuracy = ?
            WHERE id = ?
            '''
            
            conn.execute(update_query, (actual_outcome, accuracy, prediction_id))
            
            # Store result for reporting
            results.append({
                'prediction_id': prediction_id,
                'symbol': symbol,
                'prediction_type': prediction_type,
                'actual_outcome': actual_outcome,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'price_change_pct': price_change_pct,
                'accuracy': accuracy,
                'timestamp': timestamp
            })
        
        conn.commit()
        conn.close()
        market_conn.close()
        
        if not results:
            logger.info("No complete prediction results found")
            return None
        
        # Convert results to DataFrame for analysis
        results_df = pd.DataFrame(results)
        
        # Generate performance report
        report = self.generate_performance_report(results_df)
        
        # Save report
        report_path = os.path.join(self.reports_dir, f"performance_report_{datetime.now().strftime('%Y%m%d')}.json")
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=4)
        
        logger.info(f"Performance evaluation completed. Report saved to {report_path}")
        
        return report
    
    def generate_performance_report(self, results_df):
        """Generate a comprehensive performance report"""
        # Overall accuracy
        overall_accuracy = results_df['accuracy'].mean()
        
        # Accuracy by prediction type
        accuracy_by_type = results_df.groupby('prediction_type')['accuracy'].mean().to_dict()
        
        # Accuracy by symbol
        accuracy_by_symbol = results_df.groupby('symbol')['accuracy'].mean().to_dict()
        
        # Top performing symbols
        top_symbols = results_df.groupby('symbol')['accuracy'].mean().sort_values(ascending=False).head(10).to_dict()
        
        # Bottom performing symbols
        bottom_symbols = results_df.groupby('symbol')['accuracy'].mean().sort_values().head(10).to_dict()
        
        # Confusion matrix data
        confusion_data = results_df.groupby(['prediction_type', 'actual_outcome']).size().unstack(fill_value=0).to_dict()
        
        # Average price change by prediction type
        avg_price_change = results_df.groupby('prediction_type')['price_change_pct'].mean().to_dict()
        
        # Compile report
        report = {
            'generated_at': datetime.now().isoformat(),
            'overall_accuracy': overall_accuracy,
            'total_predictions': len(results_df),
            'accuracy_by_type': accuracy_by_type,
            'accuracy_by_symbol': accuracy_by_symbol,
            'top_performing_symbols': top_symbols,
            'bottom_performing_symbols': bottom_symbols,
            'confusion_matrix': confusion_data,
            'avg_price_change_by_prediction': avg_price_change
        }
        
        return report
