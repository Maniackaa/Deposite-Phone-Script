import asyncio
import json
import time

import aiohttp
import requests
from aiohttp import ClientTimeout

from config.bot_settings import logger, settings


data = {
    'refresh': '',
    'access': ''
}


async def get_token():
    logger.info('Получение первичного токена по логину')
    try:
        login = settings.LOGIN
        password = settings.PASSWORD
        url = f"{settings.HOST}/api/v1/token/"
        payload = json.dumps({
            "username": login,
            "password": password
        })
        headers = {'Content-Type': 'application/json'}
        print(url)
        response = requests.request("POST", url, headers=headers, data=payload)
        logger.info(response.status_code)
        token_dict = response.json()
        data['refresh'] = token_dict.get('refresh')
        data['access'] = token_dict.get('access')
        logger.info(f'data: {data}')
        return token_dict
    except Exception as err:
        logger.error(f'Ошибка получения токена по логину/паролю: {err}')
        raise err


async def refresh_token() -> str:
    logger.info('Обновление токена')
    try:
        url = f"{settings.HOST}/api/v1/token/refresh/"
        payload = json.dumps({
            "refresh": data['refresh']
        })
        headers = {'Content-Type': 'application/json'}
        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code == 401:
            await get_token()
            return data['access']
        token_dict = response.json()
        print(token_dict)
        access_token = token_dict.get('access')
        logger.debug(f'access_token: {access_token}')
        data['access'] = access_token
        logger.info(f'data: {data}')
        return access_token
    except Exception as err:
        logger.error(f'Ошибка обновления токена: {err}')


async def check_payment(payment_id, count=0) -> dict:

    url = f"{settings.HOST}/api/v1/payment_status/{payment_id}/"
    logger.info(f'Проверка статуса {url}')
    headers = {
        'Authorization': f'Bearer {data["access"]}'
    }
    response = requests.request("GET", url, headers=headers)
    logger.debug(response.status_code)
    if response.status_code == 401:
        logger.info('Обновляем токен')
        await refresh_token()
        await asyncio.sleep(count)
        return await check_payment(payment_id, count=count+1)
    return response.json()


async def change_payment_status(payment_id: str, status: int):
    """Смена статуса платежа"""
    try:
        logger.debug(f'Смена статуса платежа {payment_id} на: {status}')
        url = f'{settings.HOST}/api/v1/payment_status/{payment_id}/'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {data["access"]}'
                   }
        json_data = {
            'status': status,
        }
        async with aiohttp.ClientSession(timeout=ClientTimeout(5)) as session:
            async with session.put(url, headers=headers, json=json_data, ssl=False) as response:
                if response.status == 200:
                    logger.debug(f'Статус {payment_id} изменен на {status}')
                else:
                    logger.warning(f'Статус {payment_id} НЕ ИЗМЕНЕН! {response.status}')
                result = await response.json()
                logger.debug(result)
        return result
    except Exception as err:
        logger.error(f'Ошибка при смене статуса платежа: {err}')
        raise err


async def main():
    await change_payment_status('21fc7181-a6c0-4c60-8130-c17742b2c84d', 3)
    await change_payment_status('21fc7181-a6c0-4c60-8130-c17742b2c84d', 5)

if __name__ == '__main__':
    asyncio.run(get_token())
    asyncio.run(refresh_token())
    asyncio.run(main())
