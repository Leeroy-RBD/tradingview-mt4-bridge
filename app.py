#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TradingView to MT5 Bridge Server avec Mapping des symboles
Reçoit les alertes TradingView et les expose à MetaTrader 5
"""

from flask import Flask, request, jsonify
from datetime import datetime
import json
import os
import hashlib

app = Flask(__name__)

# Configuration de sécurité
SECRET_PASSWORD = os.environ.get('BRIDGE_PASSWORD', 'CHANGEZ_MOI_ABSOLUMENT')

# ╔══════════════════════════════════════════════════════════════╗
# ║  MAPPING DES SYMBOLES TradingView → MT5                     ║
# ╚══════════════════════════════════════════════════════════════╝
SYMBOL_MAPPING = {
    # Indices US
    "SPX": "US500.cash",
    "US500": "US500.cash",
    "SPX500": "US500.cash",
    "NAS100": "NAS100.cash",
    "NASDAQ": "NAS100.cash",
    "US30": "US30.cash",
    "DJI": "US30.cash",
    "US100": "NAS100.cash",
    
    # Indices Européens
    "DAX": "GER40.cash",
    "GER30": "GER40.cash",
    "FTSE": "UK100.cash",
    "CAC40": "FRA40.cash",
    
    # Forex
    "EURUSD": "EURUSD",
    "GBPUSD": "GBPUSD",
    "USDJPY": "USDJPY",
    "AUDUSD": "AUDUSD",
    "USDCAD": "USDCAD",
    "USDCHF": "USDCHF",
    "NZDUSD": "NZDUSD",
    "EURGBP": "EURGBP",
    "EURJPY": "EURJPY",
    "GBPJPY": "GBPJPY",
    
    # Métaux
    "XAUUSD": "XAUUSD",
    "GOLD": "XAUUSD",
    "XAGUSD": "XAGUSD",
    "SILVER": "XAGUSD",
    
    # Crypto
    "BTCUSD": "BTCUSD",
    "ETHUSD": "ETHUSD",
    "BITCOIN": "BTCUSD",
    "ETHEREUM": "ETHUSD",
    
    # Matières premières
    "USOIL": "USOIL.cash",
    "WTI": "USOIL.cash",
    "UKOIL": "UKOIL.cash",
    "BRENT": "UKOIL.cash",
}

signal_storage = {
    'last_signal': None,
    'signal_id': None,
    'timestamp': None
}

def map_symbol(tv_symbol):
    """
    Convertit un symbole TradingView vers le format MT5
    Gère les majuscules et retourne le symbole mappé ou original
    """
    tv_symbol_upper = tv_symbol.upper().strip()
    
    # Cherche dans le mapping
    if tv_symbol_upper in SYMBOL_MAPPING:
        mt5_symbol = SYMBOL_MAPPING[tv_symbol_upper]
        print(f"🔀 Mapping: {tv_symbol} → {mt5_symbol}")
        return mt5_symbol
    
    # Si pas de mapping, retourne le symbole original
    print(f"ℹ️  Pas de mapping pour {tv_symbol}, utilisation du nom original")
    return tv_symbol

def generate_signal_id(data):
    """Génère un ID unique pour chaque signal"""
    unique_string = f"{data['action']}{data['symbol']}{data.get('sl', '')}{data.get('tp', '')}{datetime.utcnow().isoformat()}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

def validate_signal(data):
    """Valide les données reçues de TradingView"""
    required_fields = ['action', 'symbol', 'pass']
    
    for field in required_fields:
        if field not in data:
            return False, f"Champ manquant: {field}"
    
    if data['pass'] != SECRET_PASSWORD:
        return False, "Mot de passe incorrect"
    
    if data['action'].lower() not in ['buy', 'sell', 'close', 'close_all']:
        return False, "Action invalide"
    
    return True, "OK"

@app.route('/')
def home():
    """Page d'accueil avec statut du serveur"""
    return jsonify({
        'status': 'online',
        'service': 'TradingView to MT5 Bridge',
        'version': '2.0',
        'last_signal_time': signal_storage['timestamp'],
        'has_pending_signal': signal_storage['last_signal'] is not None,
        'mapped_symbols': len(SYMBOL_MAPPING)
    })

@app.route('/mappings', methods=['GET'])
def get_mappings():
    """Retourne la liste de tous les mappings disponibles"""
    return jsonify({
        'status': 'success',
        'mappings': SYMBOL_MAPPING,
        'total': len(SYMBOL_MAPPING)
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Route pour recevoir les alertes TradingView
    Format JSON: {"action": "buy", "symbol": "SPX", "sl": "5000", "tp": "5200", "risk": "2", "pass": "password"}
    Le symbole sera automatiquement mappé vers MT5
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Aucune donnée JSON reçue'}), 400
        
        is_valid, message = validate_signal(data)
        if not is_valid:
            return jsonify({'error': message}), 403
        
        signal_id = generate_signal_id(data)
        
        # ✅ APPLICATION DU MAPPING
        original_symbol = data['symbol']
        mapped_symbol = map_symbol(original_symbol)
        
        signal_storage['last_signal'] = {
            'action': data['action'].lower(),
            'symbol': mapped_symbol,  # Symbole mappé
            'original_symbol': original_symbol,  # Symbole original TradingView
            'sl': float(data.get('sl', 0)),
            'tp': float(data.get('tp', 0)),
            'risk': float(data.get('risk', 2)),
            'signal_id': signal_id,
            'received_at': datetime.utcnow().isoformat()
        }
        signal_storage['signal_id'] = signal_id
        signal_storage['timestamp'] = datetime.utcnow().isoformat()
        
        with open('last_signal.json', 'w') as f:
            json.dump(signal_storage, f, indent=2)
        
        print(f"✅ Signal reçu: {data['action']} {original_symbol} → {mapped_symbol} - ID: {signal_id}")
        
        return jsonify({
            'status': 'success',
            'signal_id': signal_id,
            'original_symbol': original_symbol,
            'mapped_symbol': mapped_symbol,
            'message': 'Signal enregistré avec succès'
        }), 200
        
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_signal', methods=['GET'])
def get_signal():
    """Route pour que MT5 récupère le dernier signal"""
    try:
        if signal_storage['last_signal'] is None:
            return jsonify({
                'status': 'no_signal',
                'message': 'Aucun signal en attente'
            }), 200
        
        response = {
            'status': 'signal_available',
            'signal': signal_storage['last_signal']
        }
        
        print(f"📤 Signal envoyé à MT5: {signal_storage['last_signal']['action']} {signal_storage['last_signal']['symbol']}")
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/confirm_execution/<signal_id>', methods=['POST'])
def confirm_execution(signal_id):
    """MT5 confirme l'exécution d'un signal"""
    try:
        if signal_storage['signal_id'] == signal_id:
            print(f"✅ Signal {signal_id} confirmé comme exécuté")
            signal_storage['last_signal'] = None
            signal_storage['signal_id'] = None
            
            return jsonify({
                'status': 'success',
                'message': 'Exécution confirmée'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Signal ID non trouvé'
            }), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/add_mapping', methods=['POST'])
def add_mapping():
    """
    Ajoute un nouveau mapping dynamiquement
    Format: {"tv_symbol": "SPX", "mt5_symbol": "US500.cash", "pass": "password"}
    """
    try:
        data = request.get_json()
        
        if data.get('pass') != SECRET_PASSWORD:
            return jsonify({'error': 'Mot de passe incorrect'}), 403
        
        tv_symbol = data.get('tv_symbol', '').upper()
        mt5_symbol = data.get('mt5_symbol', '')
        
        if not tv_symbol or not mt5_symbol:
            return jsonify({'error': 'tv_symbol et mt5_symbol requis'}), 400
        
        SYMBOL_MAPPING[tv_symbol] = mt5_symbol
        
        # Sauvegarde du mapping
        with open('symbol_mapping.json', 'w') as f:
            json.dump(SYMBOL_MAPPING, f, indent=2)
        
        print(f"✅ Nouveau mapping ajouté: {tv_symbol} → {mt5_symbol}")
        
        return jsonify({
            'status': 'success',
            'message': f'Mapping {tv_symbol} → {mt5_symbol} ajouté',
            'total_mappings': len(SYMBOL_MAPPING)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check pour les services d'hébergement"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    # Chargement du dernier signal
    if os.path.exists('last_signal.json'):
        try:
            with open('last_signal.json', 'r') as f:
                signal_storage = json.load(f)
            print("📂 Signal précédent chargé")
        except:
            pass
    
    # Chargement des mappings personnalisés
    if os.path.exists('symbol_mapping.json'):
        try:
            with open('symbol_mapping.json', 'r') as f:
                custom_mappings = json.load(f)
                SYMBOL_MAPPING.update(custom_mappings)
            print(f"📂 {len(custom_mappings)} mappings personnalisés chargés")
        except:
            pass
    
    port = int(os.environ.get('PORT', 5000))
    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║  🚀 TradingView → MT5 Bridge Server v2.0               ║
    ║  Port: {port}                                          ║
    ║  Mappings configurés: {len(SYMBOL_MAPPING)}                      ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    app.run(host='0.0.0.0', port=port, debug=False)
