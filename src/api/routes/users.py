"""
用戶路由
"""

from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import get_user_manager, get_authenticated_user
from ..models.responses import ApiKeyResponse, SuccessResponse

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("/me")
async def get_current_user_info(
    user_id: str = Depends(get_authenticated_user),
    user_manager=Depends(get_user_manager)
):
    """
    取得當前用戶資訊

    Returns:
        dict: 用戶資訊
    """
    # 取得用戶設定
    brokers = user_manager.get_broker_names(int(user_id))

    return {
        "user_id": user_id,
        "has_broker": len(brokers) > 0,
        "brokers": brokers,
        "has_pin": user_manager.has_pin_code(int(user_id))
    }


@router.post("/api-key", response_model=ApiKeyResponse)
async def regenerate_api_key(
    user_id: str = Depends(get_authenticated_user),
    user_manager=Depends(get_user_manager)
):
    """
    重新產生 API Key

    注意：這會使舊的 API Key 失效

    Returns:
        ApiKeyResponse: 新的 API Key
    """
    try:
        new_api_key = user_manager.generate_api_key(int(user_id))

        return ApiKeyResponse(
            api_key=new_api_key,
            created_at=None  # 可以從設定檔取得
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"產生 API Key 失敗: {str(e)}"
        )


@router.get("/api-key", response_model=ApiKeyResponse)
async def get_api_key(
    user_id: str = Depends(get_authenticated_user),
    user_manager=Depends(get_user_manager)
):
    """
    取得 API Key (部分遮罩)

    Returns:
        ApiKeyResponse: API Key (遮罩)
    """
    api_key = user_manager.get_api_key(int(user_id))

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="尚未產生 API Key"
        )

    # 遮罩部分 API Key
    masked_key = api_key[:10] + "..." + api_key[-4:]

    return ApiKeyResponse(
        api_key=masked_key,
        created_at=None
    )
