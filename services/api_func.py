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


# async def check_payment(payment_id, count=0) -> dict:
#
#     url = f"{settings.HOST}/api/v1/payment_status/{payment_id}/"
#     logger.info(f'Проверка статуса {url}')
#     headers = {
#         'Authorization': f'Bearer {data["access"]}'
#     }
#     response = requests.request("GET", url, headers=headers)
#     logger.debug(response.status_code)
#     if response.status_code == 401:
#         logger.info('Обновляем токен')
#         await refresh_token()
#         await asyncio.sleep(count)
#         return await check_payment(payment_id, count=count+1)
#     return response.json()


async def check_payment(payment_id, count=0) -> dict:

    url = f"{settings.HOST}/api/v1/payment_status/{payment_id}/"
    logger.debug(f'Проверка статуса {url}')
    headers = {
        'Authorization': f'Bearer {data["access"]}'
    }
    async with aiohttp.ClientSession(timeout=ClientTimeout(10)) as session:
        async with session.put(url, headers=headers, ssl=False) as response:
            if response.status == 200:
                logger.debug(f'{response.status}')
                result = await response.json()
                return result
            elif response.status == 401:
                if count > 3:
                    return {'status': 'error check_payment'}
                logger.debug('Обновляем токен')
                await asyncio.sleep(count)
                await refresh_token()
                return await check_payment(payment_id, count=count + 1)


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
        async with aiohttp.ClientSession(timeout=ClientTimeout(10)) as session:
            async with session.put(url, headers=headers, json=json_data, ssl=False) as response:
                if response.status == 200:
                    logger.debug(f'Статус {payment_id} изменен на {status}')
                else:
                    logger.warning(f'Статус {payment_id} НЕ ИЗМЕНЕН! {response.status}')
                logger.debug(f'response.status: {response.status}')
                result = await response.json()
                logger.debug(result)
        return result
    except Exception as err:
        logger.error(f'Ошибка при смене статуса платежа: {err}')
        # raise err


async def main():
    status = 3
    await change_payment_status('8ea08ac0-b379-41af-8db3-1ea95b702eaf', status)
    await change_payment_status('f01c7a83-fe68-4b88-bee3-1875cd0744ee', status)
    await change_payment_status('7bcee34f-a56a-4206-bf00-09ffe383e43a', status)
    await change_payment_status('421385a0-1320-41c4-87c9-7a88e9960b28', status)
    await change_payment_status('8ea08ac0-b379-41af-8db3-1ea95b702eaf', status)

if __name__ == '__main__':
    asyncio.run(get_token())
    asyncio.run(refresh_token())
    asyncio.run(main())
