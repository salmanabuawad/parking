"""Camera segments (מקטעים): each camera station's coverage split into labeled segments,
each with its own set of violation types (replaces the flat camera-level rule list)."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user
from app.dependencies import get_camera_segment_repo
from app.repositories.inspector_repo import CameraSegmentRepository
from app.schemas import CameraSegmentCreate, CameraSegmentResponse, CameraSegmentUpdate

router = APIRouter(prefix="/cameras/{camera_id}/segments", tags=["camera-segments"])


@router.get("", response_model=List[CameraSegmentResponse])
def list_segments(
    camera_id: int,
    repo: CameraSegmentRepository = Depends(get_camera_segment_repo),
    _=Depends(get_current_user),
):
    return repo.list_for_camera(camera_id)


@router.post("", response_model=CameraSegmentResponse, status_code=status.HTTP_201_CREATED)
def create_segment(
    camera_id: int,
    data: CameraSegmentCreate,
    repo: CameraSegmentRepository = Depends(get_camera_segment_repo),
    _=Depends(get_current_user),
):
    return repo.create(camera_id=camera_id, **data.model_dump())


@router.patch("/{segment_id}", response_model=CameraSegmentResponse)
def update_segment(
    camera_id: int,
    segment_id: int,
    data: CameraSegmentUpdate,
    repo: CameraSegmentRepository = Depends(get_camera_segment_repo),
    _=Depends(get_current_user),
):
    seg = repo.get(segment_id)
    if not seg or seg.camera_id != camera_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")
    return repo.update(segment_id, **data.model_dump(exclude_unset=True))


@router.delete("/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_segment(
    camera_id: int,
    segment_id: int,
    repo: CameraSegmentRepository = Depends(get_camera_segment_repo),
    _=Depends(get_current_user),
):
    seg = repo.get(segment_id)
    if not seg or seg.camera_id != camera_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")
    repo.delete(segment_id)
