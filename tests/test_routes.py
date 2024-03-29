import pytest
from async_asgi_testclient import TestClient
from databases import Database
from datetime import datetime, timedelta
from sqlalchemy import and_, select
from starlette import status
from starlette.responses import JSONResponse
from typing import Any, Dict, List

from app.models import items, sendings, users
from app.schemas import (
    CreateItemResponse,
    RegisterUserResponse,
)
from main import app

JSON = Dict[str, Any]


@pytest.mark.parametrize(
    'user, register_user_request, expected_response',
    [
        (
            {
                'id': 1,
                'login': 'user',
                'password': 'password',
                'token': None,
                'token_expired_at': None,
            },
            {'login': 'user', 'password': 'password'},
            JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={'detail': 'User already exists'},
            )
        ),

        (
            None,
            {'login': 'user', 'password': 'password'},
            JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content=RegisterUserResponse(
                    detail='User has been registered'
                ).dict(),
            )
        ),
    ]
)
@pytest.mark.asyncio
async def test_register_user(
    user: JSON,
    register_user_request: JSON,
    expected_response: JSONResponse,
    database: Database,
) -> None:
    try:
        if user:
            await database.execute(users.insert().values(**user))

        async with TestClient(app) as client:
            response = await client.post('/registration', json=register_user_request)

        assert response.status_code == expected_response.status_code
        assert response.content == expected_response.body

    finally:
        await database.execute('TRUNCATE users RESTART IDENTITY CASCADE')


@pytest.mark.parametrize(
    'user, login_request, expected_status',
    [
        (
            {
                'id': 1,
                'login': 'user',
                'password': 'password',
                'token': None,
                'token_expired_at': None,
            },
            {'login': 'user', 'password': 'password'},
            status.HTTP_201_CREATED,
        ),

        (
            {
                'id': 1,
                'login': 'user',
                'password': 'password',
                'token': 'ccc06989e67e552227cbb80f952d1ac8',
                'token_expired_at': datetime.now() + timedelta(hours=1),
            },
            {'login': 'user', 'password': 'password'},
            status.HTTP_201_CREATED,
        ),

        (
            None,
            {'login': 'user', 'password': 'password'},
            status.HTTP_401_UNAUTHORIZED,
        ),
    ]
)
@pytest.mark.asyncio
async def test_login_user(
    user: JSON,
    login_request: JSON,
    expected_status: int,
    database: Database,
) -> None:
    try:
        if user:
            await database.execute(users.insert().values(**user))

        async with TestClient(app) as client:
            response = await client.post('/login', json=login_request)

        expected_token = await database.execute(
            select([users.c.token]).where(
                and_(
                    users.c.login == login_request['login'],
                    users.c.password == login_request['password'],
                )
            )
        )
        if user:
            assert response.json()['token'] == expected_token
        assert response.status_code == expected_status

    finally:
        await database.execute('TRUNCATE users RESTART IDENTITY CASCADE')


@pytest.mark.parametrize(
    'user, create_item_request, create_item_headers, expected_response',
    [
        (
            {
                'id': 1,
                'login': 'user',
                'password': 'password',
                'token': 'ccc06989e67e552227cbb80f952d1ac8',
                'token_expired_at': datetime.now() + timedelta(hours=1),
            },
            {'name': 'name'},
            {'Authorization': 'Bearer ccc06989e67e552227cbb80f952d1ac8'},
            JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content=CreateItemResponse(id=1, name='name').dict()
            )
        ),

        (
            {
                'id': 1,
                'login': 'user',
                'password': 'password',
                'token': 'ccc06989e67e552227cbb80f952d1ac8',
                'token_expired_at': datetime.now() - timedelta(hours=1),
            },
            {'name': 'name'},
            {'Authorization': 'Bearer ccc06989e67e552227cbb80f952d1ac8'},
            JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={'detail': 'Token has not been authorized'}
            )
        ),

        (
            {
                'id': 1,
                'login': 'user',
                'password': 'password',
                'token': None,
                'token_expired_at': None,
            },
            {'name': 'name'},
            {'Authorization': 'Bearer ccc06989e67e552227cbb80f952d1ac8'},
            JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={'detail': 'Token has not been authorized'}
            )
        ),
    ]
)
@pytest.mark.asyncio
async def test_create_item(
    user: JSON,
    create_item_request: JSON,
    create_item_headers: JSON,
    expected_response: JSONResponse,
    database: Database,
) -> None:
    try:
        if user:
            await database.execute(users.insert().values(**user))

        async with TestClient(app) as client:
            response = await client.post(
                '/items',
                json=create_item_request,
                headers=create_item_headers,
            )

        assert response.status_code == expected_response.status_code
        assert response.content == expected_response.body

    finally:
        await database.execute('TRUNCATE users RESTART IDENTITY CASCADE')


@pytest.mark.parametrize(
    'user, item, delete_item_request, delete_item_headers, expected_response',
    [
        (
            {
                'id': 1,
                'login': 'user',
                'password': 'password',
                'token': 'ccc06989e67e552227cbb80f952d1ac8',
                'token_expired_at': datetime.now() + timedelta(hours=1),
            },
            {'id': 1, 'user_id': 1, 'name': 'item'},
            {'id': 1},
            {'Authorization': 'Bearer ccc06989e67e552227cbb80f952d1ac8'},
            JSONResponse(
                status_code=status.HTTP_204_NO_CONTENT,
            )
        ),

        (
            {
                'id': 1,
                'login': 'user',
                'password': 'password',
                'token': 'ccc06989e67e552227cbb80f952d1ac8',
                'token_expired_at': datetime.now() + timedelta(hours=1),
            },
            None,
            {'id': 1},
            {'Authorization': 'Bearer ccc06989e67e552227cbb80f952d1ac8'},
            JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={'detail': 'Item has not been found'},
            )
        ),

        (
            {
                'id': 1,
                'login': 'user',
                'password': 'password',
                'token': None,
                'token_expired_at': None,
            },
            None,
            {'id': 1},
            {'Authorization': 'Bearer ccc06989e67e552227cbb80f952d1ac8'},
            JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={'detail': 'Token has not been authorized'}
            )
        ),
    ]
)
@pytest.mark.asyncio
async def test_delete_item(
    user: JSON,
    item: JSON,
    delete_item_request: JSON,
    delete_item_headers: JSON,
    expected_response: JSONResponse,
    database: Database,
) -> None:
    try:
        if user:
            await database.execute(users.insert().values(**user))

        if item:
            await database.execute(items.insert().values(**item))

        async with TestClient(app) as client:
            response = await client.delete(
                f'/items/{delete_item_request["id"]}',
                json=delete_item_request,
                headers=delete_item_headers,
            )

        assert response.status_code == expected_response.status_code
        assert response.content == expected_response.body

    finally:
        await database.execute('TRUNCATE users RESTART IDENTITY CASCADE')


@pytest.mark.parametrize(
    'user, items_, list_items_headers, expected_response',
    [
        (
            {
                'id': 1,
                'login': 'user',
                'password': 'password',
                'token': 'ccc06989e67e552227cbb80f952d1ac8',
                'token_expired_at': datetime.now() + timedelta(hours=1),
            },
            [
                {'id': 3, 'user_id': 1, 'name': 'item3'},
                {'id': 1, 'user_id': 1, 'name': 'item1'},
                {'id': 2, 'user_id': 1, 'name': 'item2'},
            ],
            {'Authorization': 'Bearer ccc06989e67e552227cbb80f952d1ac8'},
            JSONResponse(
                status_code=status.HTTP_200_OK,
                content=[
                    {'id': 1, 'name': 'item1'},
                    {'id': 2, 'name': 'item2'},
                    {'id': 3, 'name': 'item3'},
                ],
            )
        ),

        (
            {
                'id': 1,
                'login': 'user',
                'password': 'password',
                'token': 'ccc06989e67e552227cbb80f952d1ac8',
                'token_expired_at': datetime.now() + timedelta(hours=1),
            },
            None,
            {'Authorization': 'Bearer ccc06989e67e552227cbb80f952d1ac8'},
            JSONResponse(
                status_code=status.HTTP_200_OK,
                content=[],
            )
        ),
    ]
)
@pytest.mark.asyncio
async def test_list_items(
    user: JSON,
    items_: List[JSON],
    list_items_headers: JSON,
    expected_response: JSONResponse,
    database: Database,
) -> None:
    try:
        if user:
            await database.execute(users.insert().values(**user))

        if items_:
            await database.execute_many(items.insert(), values=items_)

        async with TestClient(app) as client:
            response = await client.get('/items', headers=list_items_headers)

        assert response.status_code == expected_response.status_code
        assert response.content == expected_response.body

    finally:
        await database.execute('TRUNCATE users RESTART IDENTITY CASCADE')


@pytest.mark.parametrize(
    'sender, sender_items, recipient, send_item_request, send_item_headers, expected_status',
    [
        (
            {
                'id': 1,
                'login': 'user1',
                'password': 'password',
                'token': 'ccc06989e67e552227cbb80f952d1ac8',
                'token_expired_at': datetime.now() + timedelta(hours=1),
            },
            [
                {'id': 3, 'user_id': 1, 'name': 'item3'},
                {'id': 1, 'user_id': 1, 'name': 'item1'},
                {'id': 2, 'user_id': 1, 'name': 'item2'},
            ],
            {
                'id': 2,
                'login': 'user2',
                'password': 'password',
                'token': None,
                'token_expired_at': None,
            },
            {'id': 3, 'recipient_login': 'user2'},
            {'Authorization': 'Bearer ccc06989e67e552227cbb80f952d1ac8'},
            status.HTTP_201_CREATED,
        ),

        (
            {
                'id': 1,
                'login': 'user1',
                'password': 'password',
                'token': 'ccc06989e67e552227cbb80f952d1ac8',
                'token_expired_at': datetime.now() + timedelta(hours=1),
            },
            [
                {'id': 3, 'user_id': 1, 'name': 'item3'},
                {'id': 1, 'user_id': 1, 'name': 'item1'},
                {'id': 2, 'user_id': 1, 'name': 'item2'},
            ],
            None,
            {
                'id': 3,
                'recipient_login': 'user1',
            },
            {'Authorization': 'Bearer ccc06989e67e552227cbb80f952d1ac8'},
            status.HTTP_400_BAD_REQUEST,
        ),

        (
            {
                'id': 1,
                'login': 'user1',
                'password': 'password',
                'token': 'ccc06989e67e552227cbb80f952d1ac8',
                'token_expired_at': datetime.now() + timedelta(hours=1),
            },
            [
                {'id': 3, 'user_id': 1, 'name': 'item3'},
                {'id': 1, 'user_id': 1, 'name': 'item1'},
                {'id': 2, 'user_id': 1, 'name': 'item2'},
            ],
            {
                'id': 2,
                'login': 'user2',
                'password': 'password',
                'token': None,
                'token_expired_at': None,
            },
            {'id': 99, 'recipient_login': 'user2'},
            {'Authorization': 'Bearer ccc06989e67e552227cbb80f952d1ac8'},
            status.HTTP_404_NOT_FOUND,
        ),

        (
            {
                'id': 1,
                'login': 'user1',
                'password': 'password',
                'token': 'ccc06989e67e552227cbb80f952d1ac8',
                'token_expired_at': datetime.now() + timedelta(hours=1),
            },
            [
                {'id': 3, 'user_id': 1, 'name': 'item3'},
                {'id': 1, 'user_id': 1, 'name': 'item1'},
                {'id': 2, 'user_id': 1, 'name': 'item2'},
            ],
            None,
            {'id': 3, 'recipient_login': 'user2'},
            {'Authorization': 'Bearer ccc06989e67e552227cbb80f952d1ac8'},
            status.HTTP_404_NOT_FOUND,
        ),
    ]
)
@pytest.mark.asyncio
async def test_send_item(
    sender: JSON,
    sender_items: List[JSON],
    recipient: JSON,
    send_item_request: JSON,
    send_item_headers: JSON,
    expected_status: int,
    database: Database,
) -> None:
    try:
        if sender:
            await database.execute(users.insert().values(**sender))
        if recipient:
            await database.execute(users.insert().values(**recipient))
        if sender_items:
            await database.execute_many(items.insert(), values=sender_items)

        async with TestClient(app) as client:
            response = await client.post(
                '/send',
                json=send_item_request,
                headers=send_item_headers,
            )

        assert response.status_code == expected_status

    finally:
        await database.execute('TRUNCATE users RESTART IDENTITY CASCADE')


@pytest.mark.parametrize(
    'sender, sender_items, recipient, item_sending, '
    'confirm_sending_request, confirm_sending_headers, expected_status',
    [
        (
            {
                'id': 1,
                'login': 'user1',
                'password': 'password',
                'token': None,
                'token_expired_at': None,
            },
            [
                {'id': 3, 'user_id': 1, 'name': 'item3'},
                {'id': 1, 'user_id': 1, 'name': 'item1'},
                {'id': 2, 'user_id': 1, 'name': 'item2'},
            ],
            {
                'id': 2,
                'login': 'user2',
                'password': 'password',
                'token': 'ccc06989e67e552227cbb80f952d1ac8',
                'token_expired_at': datetime.now() + timedelta(hours=1),
            },
            {
                'id': 1,
                'item_id': 3,
                'from_user_id': 1,
                'to_user_id': 2,
                'item_token': 'a185a9ad7b1b3d166702ba97b83e9e17',
            },
            {'item_token': 'a185a9ad7b1b3d166702ba97b83e9e17'},
            {'Authorization': 'Bearer ccc06989e67e552227cbb80f952d1ac8'},
            status.HTTP_200_OK,
        ),

        (
            None,
            None,
            None,
            None,
            {'item_token': 'a185a9ad7b1b3d166702ba97b83e9e17'},
            {'Authorization': 'Bearer ccc06989e67e552227cbb80f952d1ac8'},
            status.HTTP_401_UNAUTHORIZED,
        ),

        (
            {
                'id': 1,
                'login': 'user1',
                'password': 'password',
                'token': None,
                'token_expired_at': None,
            },
            [
                {'id': 3, 'user_id': 1, 'name': 'item3'},
                {'id': 1, 'user_id': 1, 'name': 'item1'},
                {'id': 2, 'user_id': 1, 'name': 'item2'},
            ],
            {
                'id': 2,
                'login': 'user2',
                'password': 'password',
                'token': 'ccc06989e67e552227cbb80f952d1ac8',
                'token_expired_at': datetime.now() + timedelta(hours=1),
            },
            None,
            {'item_token': 'a185a9ad7b1b3d166702ba97b83e9e17'},
            {'Authorization': 'Bearer ccc06989e67e552227cbb80f952d1ac8'},
            status.HTTP_404_NOT_FOUND,
        ),
    ]
)
@pytest.mark.asyncio
async def test_confirm_sending(
    sender: JSON,
    sender_items: List[JSON],
    recipient: JSON,
    item_sending: JSON,
    confirm_sending_request: JSON,
    confirm_sending_headers: JSON,
    expected_status: int,
    database: Database,
) -> None:
    try:
        if sender:
            await database.execute(users.insert().values(**sender))
        if sender_items:
            await database.execute_many(items.insert(), values=sender_items)
        if recipient:
            await database.execute(users.insert().values(**recipient))
        if item_sending:
            await database.execute(sendings.insert().values(**item_sending))

        async with TestClient(app) as client:
            response = await client.get(
                '/confirm',
                query_string=confirm_sending_request,
                headers=confirm_sending_headers,
            )

        assert response.status_code == expected_status

    finally:
        await database.execute('TRUNCATE users RESTART IDENTITY CASCADE')
