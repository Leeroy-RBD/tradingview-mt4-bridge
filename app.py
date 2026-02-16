#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TradingView to MT4 Bridge Server
Reçoit les alertes TradingView et les expose à MetaTrader 4
"""

from flask import Flask, request, jsonify
from datetime import datetime
import json
import os
import hashlib

app = Flask(__name__)

# Configuration de sécurité
SECRET_PASSWORD = os.environ.get('BRIDGE_PASSWORD', 'Lr06022002')
signal_storage = {
    'last_signal': None,
    'signal_id': None,
    'timestamp': None
}

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
        'service': 'TradingView to MT4 Bridge',
        'last_signal_time': signal_storage['timestamp'],
        'has_pending_signal': signal_storage['last_signal'] is not None
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Route pour recevoir les alertes TradingView
    Format JSON: {"action": "buy", "symbol": "EURUSD", "sl": "1.0850", "tp": "1.0950", "risk": "2", "pass": "password"}
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Aucune donnée JSON reçue'}), 400
        
        is_valid, message = validate_signal(data)
        if not is_valid:
            return jsonify({'error': message}), 403
        
        signal_id = generate_signal_id(data)
        
        signal_storage['last_signal'] = {
            'action': data['action'].lower(),
            'symbol': data['symbol'].upper(),
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
        
        print(f"✅ Signal reçu: {data['action']} {data['symbol']} - ID: {signal_id}")
        
        return jsonify({
            'status': 'success',
            'signal_id': signal_id,
            'message': 'Signal enregistré avec succès'
        }), 200
        
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_signal', methods=['GET'])
def get_signal():
    """Route pour que MT4 récupère le dernier signal"""
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
        
        print(f"📤 Signal envoyé à MT4: {signal_storage['last_signal']['action']} {signal_storage['last_signal']['symbol']}")
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/confirm_execution/<signal_id>', methods=['POST'])
def confirm_execution(signal_id):
    """MT4 confirme l'exécution d'un signal"""
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

@app.route('/health', methods=['GET'])
def health():
    """Health check pour les services d'hébergement"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    if os.path.exists('last_signal.json'):
        try:
            with open('last_signal.json', 'r') as f:
                signal_storage = json.load(f)
            print("📂 Signal précédent chargé")
        except:
            pass
    
    port = int(os.environ.get('PORT', 5000))
    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║  🚀 TradingView → MT4 Bridge Server                     ║
    ║  Port: {port}                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    app.run(host='0.0.0.0', port=port, debug=False)
