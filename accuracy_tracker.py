import sqlite3
import logging
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class AccuracyTracker:
    def __init__(self, db_path='data', ai_model=None):
        self.db_path = db_path
        self.ai_model = ai_model
        
        logger.info("Accuracy tracker initialized")
    
    def track_prediction_outcomes(self):
        """Track outcomes of predictions and update accuracy metrics"""
        conn = sqlite3.connect(os.path.join(self.db_path, 'ai_model.db'))
        cursor = conn.cursor()
        
        # Get predictions without outcomes (accuracy is NULL)
        cursor.execute('''
        SELECT id, symbol, prediction_type, confidence_score, timestamp, features_id
        FROM model_predictions
        WHERE actual_outcome IS NULL AND timestamp < ?
        ''', (int((datetime.now() - timedelta(hours=1)).timestamp() * 1000),))  # Only check predictions older than 1 hour
        
        predictions = cursor.fetchall()
        
        if not predictions:
            logger.info("No predictions to track outcomes for")
            conn.close()
            return
        
        logger.info(f"Tracking outcomes for {len(predictions)} predictions")
        
        # Get market data for outcome determination
        market_conn = sqlite3.connect(os.path.join(self.db_path, 'market_data.db'))
        market_cursor = market_conn.cursor()
        
        for pred_id, symbol, pred_type, confidence, timestamp, features_id in predictions:
            # Get price at prediction time
            market_cursor.execute('''
            SELECT price FROM market_data
            WHERE symbol = ? AND timestamp <= ?
            ORDER BY timestamp DESC LIMIT 1
            ''', (symbol, timestamp))
            
            entry_row = market_cursor.fetchone()
            
            if not entry_row:
                continue
                
            entry_price = entry_row[0]
            
            # Get price 1 hour after prediction
            future_timestamp = timestamp + (3600 * 1000)  # 1 hour in milliseconds
            
            market_cursor.execute('''
            SELECT price FROM market_data
            WHERE symbol = ? AND timestamp >= ?
            ORDER BY timestamp ASC LIMIT 1
            ''', (symbol, future_timestamp))
            
            exit_row = market_cursor.fetchone()
            
            if not exit_row:
                continue
                
            exit_price = exit_row[0]
            
            # Calculate price change
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
            accuracy = 1.0 if pred_type == actual_outcome else 0.0
            
            # Update prediction with actual outcome
            cursor.execute('''
            UPDATE model_predictions
            SET actual_outcome = ?, accuracy = ?
            WHERE id = ?
            ''', (actual_outcome, accuracy, pred_id))
            
            logger.debug(f"Updated prediction {pred_id} for {symbol}: {pred_type} -> {actual_outcome} (Accuracy: {accuracy})")
        
        conn.commit()
        conn.close()
        market_conn.close()
        
        logger.info("Finished tracking prediction outcomes")
    
    def analyze_model_performance(self):
        """Analyze model performance and provide insights"""
        conn = sqlite3.connect(os.path.join(self.db_path, 'ai_model.db'))
        
        # Get overall accuracy
        query = '''
        SELECT AVG(accuracy) * 100 as overall_accuracy,
               COUNT(*) as total_predictions
        FROM model_predictions
        WHERE accuracy IS NOT NULL
        '''
        
        cursor = conn.cursor()
        cursor.execute(query)
        overall_row = cursor.fetchone()
        
        if not overall_row or overall_row[1] < 10:  # Need at least 10 predictions
            logger.info("Not enough data for performance analysis")
            conn.close()
            return None
        
        overall_accuracy = overall_row[0]
        total_predictions = overall_row[1]
        
        # Get accuracy by symbol
        query = '''
        SELECT symbol, 
               AVG(accuracy) * 100 as symbol_accuracy,
               COUNT(*) as prediction_count
        FROM model_predictions
        WHERE accuracy IS NOT NULL
        GROUP BY symbol
        HAVING COUNT(*) >= 5
        ORDER BY symbol_accuracy DESC
        '''
        
        df_symbols = pd.read_sql_query(query, conn)
        
        # Get accuracy by prediction type
        query = '''
        SELECT prediction_type, 
               AVG(accuracy) * 100 as type_accuracy,
               COUNT(*) as prediction_count
        FROM model_predictions
        WHERE accuracy IS NOT NULL
        GROUP BY prediction_type
        '''
        
        df_types = pd.read_sql_query(query, conn)
        
        # Get accuracy by confidence level
        query = '''
        SELECT 
            CASE 
                WHEN confidence_score < 0.6 THEN 'Low (<60%)'
                WHEN confidence_score < 0.8 THEN 'Medium (60-80%)'
                ELSE 'High (>80%)'
            END as confidence_level,
            AVG(accuracy) * 100 as level_accuracy,
            COUNT(*) as prediction_count
        FROM model_predictions
        WHERE accuracy IS NOT NULL
        GROUP BY confidence_level
        '''
        
        df_confidence = pd.read_sql_query(query, conn)
        
        # Get accuracy trend over time
        query = '''
        SELECT date(datetime(timestamp/1000, 'unixepoch')) as date,
               AVG(accuracy) * 100 as daily_accuracy,
               COUNT(*) as daily_count
        FROM model_predictions
        WHERE accuracy IS NOT NULL
        GROUP BY date
        ORDER BY date
        '''
        
        df_trend = pd.read_sql_query(query, conn)
        
        conn.close()
        
        # Compile analysis results
        analysis = {
            'overall_accuracy': overall_accuracy,
            'total_predictions': total_predictions,
            'best_symbols': df_symbols.head(5)[['symbol', 'symbol_accuracy', 'prediction_count']].to_dict('records'),
            'worst_symbols': df_symbols.tail(5)[['symbol', 'symbol_accuracy', 'prediction_count']].to_dict('records'),
            'accuracy_by_type': df_types[['prediction_type', 'type_accuracy', 'prediction_count']].to_dict('records'),
            'accuracy_by_confidence': df_confidence[['confidence_level', 'level_accuracy', 'prediction_count']].to_dict('records'),
            'accuracy_trend': {
                'dates': df_trend['date'].tolist(),
                'values': df_trend['daily_accuracy'].tolist(),
                'counts': df_trend['daily_count'].tolist()
            }
        }
        
        # Calculate improvement
        if len(df_trend) >= 2:
            first_week = df_trend.head(min(7, len(df_trend) // 2))['daily_accuracy'].mean()
            last_week = df_trend.tail(min(7, len(df_trend) // 2))['daily_accuracy'].mean()
            
            analysis['accuracy_improvement'] = last_week - first_week
        else:
            analysis['accuracy_improvement'] = 0
        
        # Log insights
        logger.info(f"Model performance analysis: Overall accuracy: {overall_accuracy:.2f}% ({total_predictions} predictions)")
        
        if analysis['accuracy_improvement'] > 0:
            logger.info(f"Model is improving: +{analysis['accuracy_improvement']:.2f}% accuracy improvement")
        elif analysis['accuracy_improvement'] < 0:
            logger.info(f"Model is declining: {analysis['accuracy_improvement']:.2f}% accuracy decline")
        
        return analysis
    
    def adjust_model_parameters(self):
        """Adjust AI model parameters based on performance analysis"""
        if not self.ai_model:
            logger.warning("No AI model provided for parameter adjustment")
            return
        
        # Get performance analysis
        analysis = self.analyze_model_performance()
        
        if not analysis:
            return
        
        # Identify underperforming symbols
        underperforming = [s['symbol'] for s in analysis['worst_symbols'] if s['symbol_accuracy'] < 40]
        
        for symbol in underperforming:
            logger.info(f"Triggering retraining for underperforming symbol: {symbol}")
            
            # Force model retraining for this symbol
            if hasattr(self.ai_model, 'train_advanced_models'):
                self.ai_model.train_advanced_models(symbol)
