import asyncio
import datetime

import requests
import uvicorn
from fastapi import FastAPI, Request
from starlette.responses import HTMLResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from config.bot_settings import get_my_loggers, settings, tz
from database.db import PhoneDB, PhoneDevice, last_phone_name
from services.api_func import get_token, refresh_token, check_payment, change_payment_status
from services.func import read_phones_from_db, get_phone_from_pk, refresh_phones_condition, \
    make_screenshot, get_next_device_name, get_phone_device_from_name
from steps.step_1_card_input import insert_card_data
from steps.step_2_sms_code_input import insert_sms_code

app = FastAPI()
app.mount("/media", StaticFiles(directory="media"), name='media')
# HOST = 'https://asu-payme.com'
HOST = settings.HOST

logger = get_my_loggers()


# async def get_status(payment_id):
#     try:
#         response = requests.get(url=f'{settings.HOST}/api/payment/{payment_id}/',
#                                 data={
#                                     'id': f'{payment_id}'}
#                                 )
#         status = response.json().get('status')
#         logger.debug(f'status {payment_id}: {status}')
#         return int(status)
#     except Exception as err:
#         logger.error('Ошибка при запросе статуса: err')
#

async def job(phone: PhoneDevice, data: dict):
    """Работа телефона.
    1. Ввод данных карты и ожидание sms
    2. Ввод смс-кода
    """
    try:
        payment_id = data['payment_id']
        phone.db.set('current_status', PhoneDB.PhoneStatus.IN_PROGRESS)
        phone.db.set('payment_id', payment_id)
        adb_device = phone.device
        job_logger = get_my_loggers().bind(phone=phone, payment_id=payment_id)
        job_logger.info(F'Телефон {phone} start job {data}')

        payment_check = await check_payment(payment_id)
        status = payment_check.get('status')
        print('status:', status)
        if str(status) != '3':
            job_logger.warning(f'Некорректный статус: {status}')
            return

        # # Меняем статус на 4 Отправлено боту
        # response = requests.patch(url=f'{settings.HOST}/api/v1/payment_status/',
        #                           data={'id': payment_id, 'status': 4})
        await change_payment_status(payment_id, 4)
        job_logger.debug('Изменен статус на 4. Отправлено боту')
        # Ввод данных карты
        await insert_card_data(adb_device, data=data)
        # Меняем статус на 5 Ожидание смс

        await change_payment_status(payment_id, 5)
        phone.db.set('current_status', PhoneDB.PhoneStatus.WAIT_SMS)

        sms = ''
        step_2_required = data['step_2_required']
        logger.debug(f'step_2_required: {step_2_required}')
        start_time = datetime.datetime.now()
        if step_2_required:
            job_logger.debug('Статус 5 Ожидание смс')
            while not sms:
                await asyncio.sleep(3)
                total_time = datetime.datetime.now() - start_time
                if total_time > datetime.timedelta(minutes=3):
                    job_logger.debug('Ожидание вышло')
                    return False
                # response = requests.get(
                #     url=f'{settings.HOST}/api/v1/payment/{payment_id}/')
                response_data = await check_payment(payment_id)
                logger.debug(f'response_data: {response_data}')
                sms = response_data.get('sms_code')
                job_logger.debug(f'Ожидание sms_code {sms}')
            job_logger.info(f'Получен код смс: {sms}')
            await insert_sms_code(adb_device, data, sms)
        # Меняем статус на 6 Бот отработал
        await change_payment_status(payment_id, 6)
        await asyncio.sleep(5)
        phone.db.set('current_status', PhoneDB.PhoneStatus.READY)
        await make_screenshot(phone.device)
        phone.db.set('image', f'media/{phone.device.serial}.png')
        job_logger.debug('Статус 6 Бот отработал. Конец')
    except ConnectionError:
        logger.warning('Сервер не доступен')
    except Exception as err:
        logger.error(err)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request, payment_id: str,
               amount: str,
               card_number: str,
               expired_month: int,
               expired_year: int,
               cvv: int,
               name: str,
               step_1: bool = False,
               step_2_required: bool = False,
               step_2_x: int = 0,
               step_2_y: int = 0,
               step_3_x: int = 0,
               step_3_y: int = 0,
               owner_name: str = "",
               sms_code: str | None = None,):
    try:
        logger.debug(f'payment_id: {payment_id}')
        phone_name = get_next_device_name()
        phone = get_phone_device_from_name(phone_name)
        if phone:
            phone.db.set('payment_id', payment_id)
            phone.db.set('amount', amount)
            logger.info(f'Выбран телефон {phone.device.serial}')
            data = {
                'payment_id': payment_id,
                'owner_name': owner_name,
                'amount': amount,
                'card_number': card_number,
                'expired_month': f'{expired_month:02d}',
                'expired_year': expired_year,
                'cvv': cvv,
                'name': name,
                'step_1': step_1,
                'step_2_required': step_2_required,
                'step_2_x': step_2_x,
                'step_2_y': step_2_y,
                'step_3_x': step_3_x,
                'step_3_y': step_3_y,
            }
            # Запускаем телефон
            asyncio.create_task(job(phone, data))

            script = f"""<script>
function getData() {{
            var xhr = new XMLHttpRequest();
            xhr.open("POST", "{settings.HOST}/api/v1/payment_status/", true);
            xhr.setRequestHeader("Content-Type", "application/json");

            xhr.onload = function () {{
                if (xhr.status >= 200 && xhr.status < 300) {{
                    var jsonResponse = JSON.parse(xhr.responseText);

                    // Вывод результата "status" в тег с id="status"
                    document.getElementById("status").innerText = jsonResponse.status;

                    // Вывод результата "sms" в тег с id="sms"
                    document.getElementById("sms").innerText = jsonResponse.sms;
                }} else {{
                    console.error(xhr.statusText);
                }}
            }};

            xhr.onerror = function () {{
                console.error("Request failed");
            }};

            xhr.send(JSON.stringify({{ id: "{payment_id}" }}));
        }}

        // Вызов функции getData каждую секунду
        getData(); // вызов для первоначального получения данных
        setInterval(getData, 3000); // вызов каждую секунду
           </script>"""

            tag_data = """
            <h3>Платеж <a href='{host}/payments/{payment_id}/'>{payment_id}</a></h3>
            <h3>Сумма {amount}</h3>
            <h4>Телефон: {device_serial}</h4>
            {card_number}<br>
            {expired_month}/{expired_year}<br>
            <br>Тип: <b>{name}</b>
            <div>
              <p>SMS: <span id="sms"></span></p>
              <p>Status: <span id="status"></span></p>
            </div>
            {script}
            """
            return HTMLResponse(content=tag_data.format(host=settings.HOST,
                payment_id=payment_id, amount=amount, device_serial=f'{phone_name}: {phone.device.serial}',
                card_number=card_number, expired_month=expired_month, expired_year=expired_year, name=data['name'],
                sms='sms', script=None))

        else:
            return "Телефон не найден"

    except ConnectionError as err:
        logger.error(err)

    except Exception as err:
        logger.error(err)
        raise err


script2 = """
function sendGetRequest(pk) {
    console.log(pk);
     fetch("http://127.0.0.1:3000/phone_status_ready?phonedb_id=${id}", {method: "GET"});
}
"""


@app.get("/home", response_class=HTMLResponse)
async def root(request: Request):
    refresh_phones_condition()
    phones = read_phones_from_db()
    templates = Jinja2Templates(directory="templates")
    context = {
            "request": request,
            "phones": phones,
            "script2": script2,
            "last_phone_name": last_phone_name[0]
        }
    return templates.TemplateResponse(
        "phone_control.html",
        context
    )


@app.get("/phone_status_ready")
async def root(request: Request, phonedb_id: int):
    logger.info(phonedb_id)
    phone_db: PhoneDB = get_phone_from_pk(phonedb_id)
    print(phone_db)
    if phone_db.is_active:
        phone_db.set('current_status', PhoneDB.PhoneStatus.READY)
        phone_db.set('image', None)
        return True


@app.post("/merchtest/")
async def test(request: Request):
    print(await request.json())
    return True


if __name__ == "__main__":
    try:
        logger.debug('start app')
        token = asyncio.run(get_token())
        if not token.get('access'):
            raise ValueError('Неверный пароль/логин')
        asyncio.run(refresh_token())
        uvicorn.run(app, host="127.0.0.1", port=3000)
    except KeyboardInterrupt:
        logger.info('Stoped')
    except Exception as err:
        raise err

