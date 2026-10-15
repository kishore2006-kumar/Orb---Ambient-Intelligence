"""Device API endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from hub.api.deps import get_db, require_hub_token
from hub.db.models import Device
from hub.schemas import (
    AdbConnectRequest,
    AdbPairRequest,
    DeviceOut,
    IosStubDeviceRequest,
    PairConfirmRequest,
    PairConfirmResponse,
    PairStartRequest,
    PairStartResponse,
    VirtualDeviceRequest,
)
from hub.services import devices as device_svc
from hub.services import pairing as pairing_svc

router = APIRouter()


def _device_to_out(device: Device) -> DeviceOut:
    return DeviceOut(
        id=device.id,
        name=device.name,
        type=device.type,
        os=device.os,
        driver=device.driver,
        status=device.status,
        battery=device.battery,
        state=dict(device.state_json or {}),
        capabilities=[c.capability for c in device.capabilities],
        last_seen=device.last_seen,
    )


@router.post("/devices/pair/start", dependencies=[Depends(require_hub_token)])
def pair_start(
    body: PairStartRequest,
    db: Annotated[Session, Depends(get_db)],
) -> PairStartResponse:
    pairing = pairing_svc.start_pairing(db, body.device_type, body.os)
    return PairStartResponse(code=pairing.code, expires_at=pairing.expires_at)


@router.post("/devices/pair/confirm", status_code=201)
def pair_confirm(
    body: PairConfirmRequest,
    db: Annotated[Session, Depends(get_db)],
) -> PairConfirmResponse:
    result = pairing_svc.confirm_pairing(db, body.code, body.name, body.capabilities)
    return PairConfirmResponse(
        device_id=result["device_id"],
        device_token=result["device_token"],
    )


@router.post("/devices/adb/pair", status_code=201, dependencies=[Depends(require_hub_token)])
def adb_pair(
    body: AdbPairRequest,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> DeviceOut:
    adb_runner = getattr(request.app.state, "adb_runner", None)
    settings = request.app.state.settings
    device = device_svc.pair_adb_device(
        db,
        name=body.name,
        device_type=body.type,
        address=body.address,
        pairing_code=body.pairing_code,
        adb_runner=adb_runner,
        settings=settings,
    )
    return _device_to_out(device)


@router.post("/devices/adb", status_code=201, dependencies=[Depends(require_hub_token)])
def adb_connect(
    body: AdbConnectRequest,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> DeviceOut:
    adb_runner = getattr(request.app.state, "adb_runner", None)
    settings = request.app.state.settings
    device = device_svc.create_adb_device(
        db,
        name=body.name,
        device_type=body.type,
        address=body.address,
        adb_runner=adb_runner,
        settings=settings,
    )
    return _device_to_out(device)


@router.post("/devices/virtual", status_code=201, dependencies=[Depends(require_hub_token)])
def create_virtual(
    body: VirtualDeviceRequest,
    db: Annotated[Session, Depends(get_db)],
) -> DeviceOut:
    device = device_svc.create_virtual_device(db, body.name, body.type, body.os)
    return _device_to_out(device)


@router.post("/devices/ios-stub", status_code=201, dependencies=[Depends(require_hub_token)])
def create_ios_stub(
    body: IosStubDeviceRequest,
    db: Annotated[Session, Depends(get_db)],
) -> DeviceOut:
    device = device_svc.create_ios_stub_device(db, body.name, body.type, body.os)
    return _device_to_out(device)


@router.get("/devices", dependencies=[Depends(require_hub_token)])
def list_devices(
    db: Annotated[Session, Depends(get_db)],
) -> list[DeviceOut]:
    return [_device_to_out(d) for d in device_svc.list_devices(db)]


@router.get("/devices/{device_id}", dependencies=[Depends(require_hub_token)])
def get_device(
    device_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> DeviceOut:
    device = device_svc.get_device(db, device_id)
    if device is None:
        raise LookupError("device_not_found")
    return _device_to_out(device)


@router.delete("/devices/{device_id}", status_code=204, dependencies=[Depends(require_hub_token)])
def delete_device(
    device_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    found = device_svc.delete_device(db, device_id)
    if not found:
        raise LookupError("device_not_found")
    return Response(status_code=204)
