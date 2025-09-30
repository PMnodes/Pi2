from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List


@dataclass
class TwitterMetadata:
    bio: str
    name: str
    user_id: str
    username: str
    created_at: datetime
    followed_count: str
    follower_count: str
    profile_picture: str
    token_expires_at: datetime
    encrypted_access_token: str
    encrypted_refresh_token: str
    twitter_account_creation_date: datetime

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TwitterMetadata":
        return cls(
            bio=data["bio"],
            name=data["name"],
            user_id=data["userId"],
            username=data["username"],
            created_at=datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00")),
            followed_count=data["followedCount"],
            follower_count=data["followerCount"],
            profile_picture=data["profilePicture"],
            token_expires_at=datetime.fromisoformat(data["tokenExpiresAt"].replace("Z", "+00:00")),
            encrypted_access_token=data["encryptedAccessToken"],
            encrypted_refresh_token=data["encryptedRefreshToken"],
            twitter_account_creation_date=datetime.fromisoformat(
                data["twitterAccountCreationDate"].replace("Z", "+00:00")
            ),
        )


@dataclass
class DiscordMetadata:
    email: str
    flags: int
    avatar: str
    user_id: str
    username: str
    verified: bool
    created_at: datetime
    global_name: str
    mfa_enabled: bool
    premium_type: int
    public_flags: int
    discriminator: str
    token_expires_at: datetime
    encrypted_access_token: str
    encrypted_refresh_token: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiscordMetadata":
        return cls(
            email=data["email"],
            flags=data["flags"],
            avatar=data["avatar"],
            user_id=data["userId"],
            username=data["username"],
            verified=data["verified"],
            created_at=datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00")),
            global_name=data["globalName"],
            mfa_enabled=data["mfaEnabled"],
            premium_type=data["premiumType"],
            public_flags=data["publicFlags"],
            discriminator=data["discriminator"],
            token_expires_at=datetime.fromisoformat(data["tokenExpiresAt"].replace("Z", "+00:00")),
            encrypted_access_token=data["encryptedAccessToken"],
            encrypted_refresh_token=data["encryptedRefreshToken"],
        )


@dataclass
class UserResponse:
    wallet_address: str
    created_at: datetime
    twitter_metadata: Optional[TwitterMetadata]
    discord_metadata: Optional[DiscordMetadata]
    telegram_metadata: Optional[Dict[str, Any]]
    has_accepted_terms: bool
    new_user: bool
    show_social_pay_tutorial: bool
    registered_on_chains: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserResponse":
        return cls(
            wallet_address=data["walletAddress"],
            created_at=datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00")),
            twitter_metadata=TwitterMetadata.from_dict(data["twitterMetadata"]) if data["twitterMetadata"] else None,
            discord_metadata=DiscordMetadata.from_dict(data["discordMetadata"]) if data["discordMetadata"] else None,
            telegram_metadata=data["telegramMetadata"],  # null → None
            has_accepted_terms=data["hasAcceptedTerms"],
            new_user=data["newUser"],
            show_social_pay_tutorial=data["showSocialPayTutorial"],
            registered_on_chains=data["registeredOnChains"],
        )


@dataclass
class ReferralData:
    code: str
    pointsObtained: Decimal
    pointsGiven: Decimal
    referredBy: Optional[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReferralData":
        return cls(
            code=data["code"],
            pointsObtained=Decimal(data["pointsObtained"]),
            pointsGiven=Decimal(data["pointsGiven"]),
            referredBy=data.get("referredBy"),
        )


@dataclass
class ClaimInfo:
    isEligible: bool
    tokensToClaim: Decimal
    tokensClaimedAt: Optional[str]
    claimTxHash: Optional[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClaimInfo":
        return cls(
            isEligible=data["isEligible"],
            tokensToClaim=Decimal(data["tokensToClaim"]),
            tokensClaimedAt=data.get("tokensClaimedAt"),
            claimTxHash=data.get("claimTxHash"),
        )


@dataclass
class EligibilityRequirements:
    inTopX: bool
    minPoints: bool
    points: bool

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EligibilityRequirements":
        return cls(
            inTopX=data["inTopX"],
            minPoints=data["minPoints"],
            points=data["points"]
        )


@dataclass
class Eligibility:
    isEligible: bool
    requirements: EligibilityRequirements

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Eligibility":
        return cls(
            isEligible=data["isEligible"],
            requirements=EligibilityRequirements.from_dict(data["requirements"]),
        )


@dataclass
class UserDataResponse:
    createdAt: datetime
    id: str
    address: str
    campaignId: str
    campaignGroup: str
    updatedAt: datetime
    booster: Decimal
    taskPoints: Decimal
    classPoints: Decimal
    classInfo: List[Any]
    totalPoints: Decimal
    scamInfo: Optional[Any]
    referralData: ReferralData
    claimInfo: ClaimInfo
    appliedBoosters: List[Any]
    rank: int
    eligibility: Eligibility

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserDataResponse":
        return cls(
            createdAt=datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00")),
            id=data["id"],
            address=data["address"],
            campaignId=data["campaignId"],
            campaignGroup=data["campaignGroup"],
            updatedAt=datetime.fromisoformat(data["updatedAt"].replace("Z", "+00:00")),
            booster=Decimal(data["booster"]),
            taskPoints=Decimal(data["taskPoints"]),
            classPoints=Decimal(data["classPoints"]),
            classInfo=data.get("classInfo", []),
            totalPoints=Decimal(data["totalPoints"]),
            scamInfo=data.get("scamInfo"),
            referralData=ReferralData.from_dict(data["referralData"]),
            claimInfo=ClaimInfo.from_dict(data["claimInfo"]),
            appliedBoosters=data.get("appliedBoosters", []),
            rank=data["rank"],
            eligibility=Eligibility.from_dict(data["eligibility"]),
        )
