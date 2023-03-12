from fastapi import APIRouter, HTTPException
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette import status
from starlette.responses import JSONResponse
from typing import List

import app.schemas as sc
from .models import ItemModel, SendingModel, SendingStatus, UserModel
from .settings import HOST, PORT

router = APIRouter()

bearer_scheme = HTTPBearer()


@router.post(
    '/registration',
    status_code=status.HTTP_201_CREATED,
    response_model=sc.RegisterUserResponse,
    description='''
    Create a user.
    '''
)
async def register_user(request: sc.RegisterUserRequest) -> sc.RegisterUserResponse:
    already_registered = await UserModel.is_registered(request.login)
    if not already_registered:
        await UserModel.create(request.login, request.password)

        registration_succeeded = await UserModel.is_registered(request.login)
        if registration_succeeded:
            return sc.RegisterUserResponse(message='User has been registered')

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT, detail='User already exists'
    )


@router.post(
    '/login',
    status_code=status.HTTP_201_CREATED,
    response_model=sc.AuthorizeUserResponse,
    description='''
    Authorize a user, return a token. Token expiration time is 24 hours.
    '''
)
async def login_user(request: sc.AuthorizeUserRequest) -> sc.AuthorizeUserResponse:
    token = await UserModel.authorize(request.login, request.password)
    if token:
        return sc.AuthorizeUserResponse(token=token)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User has not been found')


@router.post(
    '/items',
    status_code=status.HTTP_201_CREATED,
    response_model=sc.CreateItemResponse,
    description='''
    Create an item for an authorized user.
    '''
)
async def create_item(
        request: sc.CreateItemRequest,
        token: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> sc.CreateItemResponse:
    user = await UserModel.get_authorized(token.credentials)
    if user:
        item_id = await ItemModel.create(name=request.name, user_id=user['id'])
        return sc.CreateItemResponse(id=item_id, name=request.name)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Token has not been authorized',
    )


@router.delete(
    '/items/{id}',
    status_code=status.HTTP_204_NO_CONTENT,
    description='''
    Remove a particular item.
    '''
)
async def delete_item(
        request: sc.DeleteItemRequest,
        token: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> JSONResponse:
    user = await UserModel.get_authorized(token.credentials)
    if user:
        item_id = await ItemModel.delete(request.id)
        if item_id:
            return JSONResponse(
                status_code=status.HTTP_204_NO_CONTENT,
            )

        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=sc.DeleteItemResponse(message='Item has not been found').dict(),
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Token has not been authorized',
    )


@router.get(
    '/items',
    status_code=status.HTTP_200_OK,
    response_model=List[sc.ItemSchema],
    description='''
    Return a list of items for an authorized user.
    '''
)
async def list_items(
        token: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> List[sc.ItemSchema]:
    user = await UserModel.get_authorized(token.credentials)
    if user:
        items = await ItemModel.list(user_id=user['id'])
        return items

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Provided token has not been authorized',
    )


@router.post(
    '/send',
    status_code=status.HTTP_201_CREATED,
    response_model=sc.SendItemResponse,
    description='''
    Send an item, return confirmation URL.
    ''',
)
async def send_item(
        request: sc.SendItemRequest,
        token: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> sc.SendItemResponse:
    sender = await UserModel.get_authorized(token.credentials)
    if not sender:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Token has not been authorized',
        )
    if sender['login'] == request.recipient_login:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Cannot send an item to yourself',
        )

    item = await ItemModel.get(request.id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Item has not been found',
        )

    recipient = await UserModel.get_by_login(request.recipient_login)
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Recipient has not been found',
        )

    item_token = await SendingModel.initiate_sending(
        from_user_id=sender['id'], to_user_id=recipient['id'], item_id=request.id
    )
    url = f'http://{HOST}:{PORT}/get/?item_token={item_token}'
    return sc.SendItemResponse(confirmation_url=url)


@router.get(
    '/confirm',
    status_code=status.HTTP_200_OK,
    description='''
    Reassign an item to an authorized user using confirmation URL.
    ''',
)
async def confirm_sending(
        item_token: str,
        token: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> JSONResponse:
    user = await UserModel.get_authorized(token.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Token has not been authorized',
        )

    sending = await SendingModel.get(item_token)
    if not sending:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Sending has not been found',
        )

    if user['id'] != sending['to_user_id']:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='User has not been authorized for the confirmation',
        )

    sending_status = await SendingModel.complete_sending(item_token=item_token)
    if sending_status == SendingStatus.NO_SENDING:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Sending has not been found',
        )

    if sending_status == sending_status.COMPLETED:
        return JSONResponse(content={'message': 'Item has been received'})

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail='Bad request',
    )
