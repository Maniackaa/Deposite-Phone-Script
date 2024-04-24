import asyncio
import datetime

import requests
import uvicorn
from adbutils import AdbClient, AdbDevice
from fastapi import FastAPI
from starlette.responses import HTMLResponse

from config.bot_settings import get_my_loggers, settings, tz
from steps.step_1_card_input import insert_card_data
from steps.step_2_sms_code_input import insert_sms_code

app = FastAPI()

# HOST = 'https://asu-payme.com'
HOST = settings.HOST

logger = get_my_loggers()


def get_device() -> AdbDevice:
    try:
        adb_client = AdbClient(host="127.0.0.1", port=5037, socket_timeout=1)
        adb_devices = adb_client.device_list()
        logger.info(f'Подключены устройства: {adb_devices}')
        if adb_devices:
            adb_device = adb_devices[-1]
            return adb_device
    except Exception as err:
        raise err


async def get_status(payment_id):
    response = requests.get(url=f'{settings.HOST}/api/payment_status/',
                            data={
                                'id': f'{payment_id}'}
                            )
    status = response.json().get('status')
    logger.debug(f'status {payment_id}: {status}')
    return status


async def job(device, data: dict):
    """Работа телефона.
    1. Ввод данных карты и ожидание sms
    2. Ввод смс-кода
    """
    try:
        payment_id = data['payment_id']
        job_logger = get_my_loggers().bind(phone=device.serial, payment_id=payment_id)
        job_logger.debug(f'Старт job: {device.serial}, {data}')
        job_logger.info(F'Телефон {device.serial} start job {data}')

        status = await get_status(payment_id)
        if status != 3:
            job_logger.warning(f'Некорректный статус: {status}')
            return

        # # Меняем статус на 4 Отправлено боту
        response = requests.patch(url=f'{settings.HOST}/api/payment_status/',
                                  data={'id': payment_id, 'status': 4})
        job_logger.debug('Изменен статус на 4. Отправлено боту')
        # Ввод данных карты
        await insert_card_data(device, data=data)
        # Меняем статус на 5 Ожидание смс
        response = requests.patch(url=f'{settings.HOST}/api/payment_status/',
                                  data={'id': payment_id, 'status': 5})
        job_logger.debug('Статус 5 Ожидание смс')
        await asyncio.sleep(10)
        sms = ''
        step_2_required = data['step_2_required']
        start_time = datetime.datetime.now()
        while not sms or not step_2_required:
            await asyncio.sleep(3)
            total_time = datetime.datetime.now() - start_time
            if total_time > datetime.timedelta(minutes=3):
                job_logger.debug('Ожидание вышло')
                return False
            response = requests.get(
                url=f'{settings.HOST}/api/payment_status/',
                data={'id': payment_id})
            response_data = response.json()
            sms = response_data.get('sms')
            job_logger.debug(f'Ожидание sms_code {response.text}')
        if step_2_required:
            job_logger.info(f'Получен код смс: {sms}')
            await insert_sms_code(device, data, sms)
        # Меняем статус на 6 Бот отработал
        response = requests.patch(url=f'{settings.HOST}/api/payment_status/',
                                  data={'id': payment_id, 'status': 6})
        job_logger.debug('Статус 6 Бот отработал. Конец')
    except ConnectionError:
        logger.warning('Сервер не доступен')
    except Exception as err:
        logger.error(err)

@app.get("/")
async def root(payment_id: str,
               amount: str,
               owner_name: str,
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
               sms_code: str | None = None,):
    try:
        logger.debug(f'payment_id: {payment_id}')
        device = get_device()
        # device = 1
        if device:
            logger.info(f'Выбран телефон {device}')
            data = {
                'payment_id': payment_id,
                'owner_name': owner_name,
                'amount': amount,
                'device': device,
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
            asyncio.create_task(job(device, data))

            script = f"""<script>           
function getData() {{
            var xhr = new XMLHttpRequest();
            xhr.open("POST", "{settings.HOST}/api/payment_status/", true);
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
            <h3>Платеж {payment_id}</h3>
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
            return HTMLResponse(content=tag_data.format(
                payment_id=payment_id, amount=amount, device_serial=device.serial,
                card_number=card_number, expired_month=expired_month, expired_year=expired_year, name=data['name'],
                sms='sms', script=script))
        else:
            return "Телефон не найден"

    except ConnectionError as err:
        logger.error(err)

    except Exception as err:
        logger.error(err)
        raise err


if __name__ == "__main__":
    try:
        logger.debug('start app')
        uvicorn.run(app, host="127.0.0.1", port=3000)
    except KeyboardInterrupt:
        logger.info('Stoped')

