import os
import jwt
from typing import Annotated
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


security = HTTPBearer()

class AuthenticatedUser(BaseModel):
    user_id:str
    kyc_verified:bool

async def is_user_Authenticated(credentials:Annotated[HTTPAuthorizationCredentials,Depends(security)])->AuthenticatedUser:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, os.getenv('JWT_SECRET_KEY'), algorithms=[os.getenv('ALGORITHM')])

        user_id_from_req : str = payload.get('user_id')
        kyc_verified_from_req :bool = payload.get('is_kyc_verified')

        if user_id_from_req is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Can not proceed : user id not found")
        if kyc_verified_from_req is False:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Kyc not completed : can not trade")
        return AuthenticatedUser(user_id=user_id_from_req, kyc_verified=kyc_verified_from_req)

    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Referesh your login",
                            headers={"WWW-Authenticate": "Bearer"})
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Can not validate credentials : Provide proper credentials",
                            headers={"WWW-Authenticate":"Bearer"})
    
