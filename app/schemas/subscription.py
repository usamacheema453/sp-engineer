from pydantic import BaseModel

class SubscriptionStartRequest(BaseModel):
    email: str
    price_id: str

class SubscriptionStartResponse(BaseModel):
    subscription_id: str
    client_secret: str
