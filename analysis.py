# analysis.py
# Lógica de Análise e Previsão de Risco de Glicemia

import pandas as pd
from sklearn.linear_model import Ridge
from datetime import datetime, timedelta
import numpy as np
import joblib  # NECESSÁRIO para carregar/salvar o modelo
import os      # CORREÇÃO: NECESSÁRIO para usar os.path.exists

# Configuráveis
MIN_RECORDS_FOR_MODEL = 5   
LAG_PERIODS = 3             
PREDICTION_MINUTES = 30

# Constantes de Referência (Adaptadas aos padrões de glicemia)
NORMAL_RANGE_LOW = 70
NORMAL_RANGE_HIGH = 140
WARNING_HYPO = 80
WARNING_HYPER = 180

# Taxas de Mudança (mg/dL por minuto)
HYPO_DROP_RATE = -0.5
HYPER_RISE_RATE = 0.5


def calculate_rate_of_change(df):
    """
    Calcula a taxa de mudança mais recente (mg/dL por minuto)
    baseada nos dois últimos registros.
    """
    try:
        if len(df) < 2:
            return 0.0

        last_two = df.iloc[-2:].copy()
        last_two['timestamp'] = pd.to_datetime(last_two['timestamp'], utc=True)
        
        ts_diff = (last_two['timestamp'].iloc[1] - last_two['timestamp'].iloc[0]).total_seconds() / 60
        val_diff = last_two['value'].iloc[1] - last_two['value'].iloc[0]

        if ts_diff == 0:
            return 0.0
            
        rate = val_diff / ts_diff
        return rate
    except Exception as e:
        print(f"Erro ao calcular rate_of_change: {e}")
        return 0.0

def create_lag_features(df, lag=LAG_PERIODS):
    """Cria features de lag para o modelo."""
    df_lag = df.copy()
    for i in range(1, lag + 1):
        df_lag[f'value_lag_{i}'] = df_lag['value'].shift(i)
    # Remove as linhas com NaN resultantes do shift
    return df_lag.dropna()

def train_model(records, model_filepath="glucose_model.pkl"):
    """
    Treina um novo modelo Ridge e o salva.
    """
    if not records:
        print("Erro em train_model: Lista de registros vazia.")
        return None

    try:
        # Criação robusta do DataFrame
        df = pd.DataFrame(records)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.sort_values(by='timestamp').reset_index(drop=True)
        
        if len(df) < MIN_RECORDS_FOR_MODEL:
            print(f"Número insuficiente de registros para treinar o modelo ({len(df)}/{MIN_RECORDS_FOR_MODEL}).")
            return None
        
        df_features = create_lag_features(df, LAG_PERIODS)
        
        if df_features.empty:
            print("DataFrame de features vazio após a criação de lags.")
            return None

        df_features['target'] = df_features['value'].shift(-1)
        df_features = df_features.dropna() 
        
        if df_features.empty:
            print("DataFrame de treino vazio após a remoção de targets NaN.")
            return None

        features = [f'value_lag_{i}' for i in range(1, LAG_PERIODS + 1)]
        X = df_features[features]
        y = df_features['target']

        model = Ridge(alpha=1.0)
        model.fit(X, y)

        joblib.dump(model, model_filepath)
        print(f"Modelo salvo em {model_filepath}")
        return model

    except Exception as e:
        print(f"Erro em train_model: {e}")
        return None

def predict_risk_v2(records, model_filepath="glucose_model.pkl"):
    """
    Analisa o risco de glicemia usando a taxa de mudança imediata 
    e faz uma previsão usando o modelo treinado (se disponível).
    """
    try:
        if not records:
            return {
                "message": "Nenhum registro para análise.",
                "risk_level": "N/A"
            }
        
        # Criação robusta do DataFrame (Correção do erro anterior)
        df = pd.DataFrame(records)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.sort_values(by='timestamp').reset_index(drop=True)

        if df.empty:
            return {
                "message": "Registros em formato inválido para análise.",
                "risk_level": "ERROR"
            }

        ultimo = df.iloc[-1].to_dict()
        time_ultimo = ultimo['timestamp']
        predicted_value_mgdl = None
        predicted_time = None
        
        # 1. Tentar carregar/treinar o modelo
        model = None
        # CORREÇÃO: Usando os.path.exists corretamente
        if os.path.exists(model_filepath):
            try:
                model = joblib.load(model_filepath)
            except Exception as e:
                # Tenta retreinar se o modelo estiver corrompido ou o arquivo não puder ser lido
                print(f"Erro ao carregar o modelo, tentando retreinar: {e}")
                if len(df) >= MIN_RECORDS_FOR_MODEL:
                    model = train_model(records, model_filepath)
        elif len(df) >= MIN_RECORDS_FOR_MODEL:
            # Se não existe, tenta treinar se houver dados suficientes
            model = train_model(records, model_filepath)

        # 2. Previsão baseada em ML (se o modelo existe)
        if model:
            # Prepara a entrada do modelo com as features de lag
            df_lags = create_lag_features(df, LAG_PERIODS)
            if not df_lags.empty:
                last_features = df_lags.iloc[-1]
                features_cols = [f'value_lag_{i}' for i in range(1, LAG_PERIODS + 1)]
                X_pred = last_features[features_cols].values.reshape(1, -1)
                
                predicted_value_mgdl = model.predict(X_pred)[0]
                predicted_time = time_ultimo + timedelta(minutes=PREDICTION_MINUTES)
                
                # A) Risco Crítico baseado em ML
                if predicted_value_mgdl < NORMAL_RANGE_LOW:
                    message = (f"🚨 **Risco Imediato de Hipoglicemia:** A IA prevê um nível de {predicted_value_mgdl:.0f} mg/dL "
                               f"em {PREDICTION_MINUTES} minutos. Tome medidas urgentes!")
                    return {
                        "risk_level": "HIGH",
                        "message": message,
                        "predicted_time": predicted_time.isoformat(),
                        "predicted_value": predicted_value_mgdl
                    }
                elif predicted_value_mgdl > WARNING_HYPER:
                    message = (f"🚨 **Risco Imediato de Hiperglicemia:** A IA prevê um nível de {predicted_value_mgdl:.0f} mg/dL "
                               f"em {PREDICTION_MINUTES} minutos. Monitore de perto e ajuste a medicação se necessário.")
                    return {
                        "risk_level": "HIGH",
                        "message": message,
                        "predicted_time": predicted_time.isoformat(),
                        "predicted_value": predicted_value_mgdl
                    }
                elif predicted_value_mgdl > NORMAL_RANGE_HIGH or predicted_value_mgdl < WARNING_HYPO:
                    message = (f"⚠️ **Previsão de Alerta:** A IA prevê um nível de {predicted_value_mgdl:.0f} mg/dL "
                               f"em {PREDICTION_MINUTES} minutos. Fique atento e monitore novamente.")
                    return {
                        "risk_level": "MEDIUM",
                        "message": message,
                        "predicted_time": predicted_time.isoformat(),
                        "predicted_value": predicted_value_mgdl
                    }

        # 3. Análise da Taxa de Mudança (Fallback/Suplemento)
        rate_of_change = calculate_rate_of_change(df)

        # B) Risco Crítico Imediato (Baseado em valor atual)
        if ultimo['value'] <= NORMAL_RANGE_LOW:
            message = (f"🚨 **Hipoglicemia Crítica:** Seu nível atual é {ultimo['value']:.0f} mg/dL. "
                       f"Procure tratamento imediato e avise seu contato de emergência.")
            return {
                "risk_level": "HIGH",
                "message": message,
                "predicted_time": None,
                "predicted_value": None
            }
        
        # C) Risco de Queda Rápida (Baseado na taxa)
        if rate_of_change < HYPO_DROP_RATE and ultimo['value'] <= WARNING_HYPO:
            value_to_drop = ultimo['value'] - NORMAL_RANGE_LOW
            time_to_reach_alert = value_to_drop / abs(rate_of_change) if rate_of_change != 0 else float('inf')
            
            message = (f"⚠️ **Risco de Hipoglicemia:** Tendência de queda rápida ({rate_of_change:.2f} mg/dL/min). "
                       f"Pode atingir {NORMAL_RANGE_LOW} mg/dL em aproximadamente {int(time_to_reach_alert)} minutos. Tome medidas preventivas.")
            predicted_time = time_ultimo + timedelta(minutes=time_to_reach_alert)
            predicted_value_mgdl = NORMAL_RANGE_LOW
            
            return {
                "risk_level": "MEDIUM",
                "message": message,
                "predicted_time": predicted_time.isoformat() if predicted_time else None,
                "predicted_value": predicted_value_mgdl
            }
            
        # D) Risco de Subida Rápida (Baseado na taxa)
        if rate_of_change > HYPER_RISE_RATE and ultimo['value'] >= WARNING_HYPER:
            message = (f"⚠️ **Risco de Hiperglicemia:** Tendência de subida rápida ({rate_of_change:.2f} mg/dL/min). "
                       f"Siga seu plano de tratamento.")
            predicted_time = time_ultimo + timedelta(minutes=PREDICTION_MINUTES)
            
            return {
                "risk_level": "MEDIUM",
                "message": message,
                "predicted_time": predicted_time.isoformat() if predicted_time else None,
                "predicted_value": ultimo['value'] + (rate_of_change * PREDICTION_MINUTES)
            }

        # E) Situação Normal
        msg = f"Seu nível atual de glicemia ({ultimo['value']:.0f} mg/dL) está estável."
        if model and predicted_value_mgdl:
             msg += f" A previsão em 30 min é {predicted_value_mgdl:.0f} mg/dL. Continue o monitoramento."
        else:
             msg += " Continue o monitoramento."

        return {
            "risk_level": "LOW",
            "message": msg,
            "predicted_time": predicted_time.isoformat() if predicted_time else None,
            "predicted_value": predicted_value_mgdl
        }
        
    except Exception as e:
        print(f"Erro em predict_risk_v2: {e}")
        return {
            "risk_level": "ERROR",
            "message": f"Erro de processamento da análise: {e}. Verifique se o arquivo analysis.py está completo.",
            "predicted_time": None,
            "predicted_value": None
        }