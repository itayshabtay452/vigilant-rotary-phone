import re

from fastapi import APIRouter, Depends, HTTPException, Query, status  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Session  # pyright: ignore[reportMissingImports]

from app.database import get_db
from app.dependencies import verify_api_key
from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleResponse, VehicleUpdate


def _normalize_plate(plate: str) -> str:
    # Must mirror VehicleCreate._validate_plate: strip surrounding whitespace
    # and remove any embedded spaces/hyphens so URL lookups match the
    # digits-only key that was persisted at create time.
    return re.sub(r"[\s\-]", "", plate.strip())


router = APIRouter(
    prefix="/vehicles",
    tags=["vehicles"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("/", response_model=list[VehicleResponse])
def list_vehicles(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[Vehicle]:
    return (
        db.query(Vehicle)
        .order_by(Vehicle.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post("/", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
def create_vehicle(payload: VehicleCreate, db: Session = Depends(get_db)) -> Vehicle:
    existing = db.get(Vehicle, payload.license_plate)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vehicle with license plate '{payload.license_plate}' already exists",
        )

    vehicle = Vehicle(**payload.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.get("/{license_plate}", response_model=VehicleResponse)
def get_vehicle(license_plate: str, db: Session = Depends(get_db)) -> Vehicle:
    vehicle = db.get(Vehicle, _normalize_plate(license_plate))
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle with license plate '{license_plate}' not found",
        )
    return vehicle


@router.patch("/{license_plate}", response_model=VehicleResponse)
def update_vehicle(
    license_plate: str, payload: VehicleUpdate, db: Session = Depends(get_db)
) -> Vehicle:
    vehicle = db.get(Vehicle, _normalize_plate(license_plate))
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle with license plate '{license_plate}' not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vehicle, field, value)

    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.delete("/{license_plate}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(license_plate: str, db: Session = Depends(get_db)) -> None:
    vehicle = db.get(Vehicle, _normalize_plate(license_plate))
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle with license plate '{license_plate}' not found",
        )
    db.delete(vehicle)
    db.commit()
