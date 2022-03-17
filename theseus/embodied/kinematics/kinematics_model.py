# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import abc
from typing import Dict, Union

import differentiable_robot_model as drm
import torch

from theseus.geometry import SE3, LieGroup, Point2, Vector

RobotModelInput = Union[torch.Tensor, Vector]


class KinematicsModel(abc.ABC):
    def __init__(self):
        pass

    @abc.abstractmethod
    def forward_kinematics(self, robot_pose: RobotModelInput) -> Dict[str, LieGroup]:
        pass

    @abc.abstractmethod
    def dim(self) -> int:
        pass


class IdentityModel(KinematicsModel):
    def __init__(self):
        super().__init__()

    def forward_kinematics(self, robot_pose: RobotModelInput) -> Dict[str, LieGroup]:
        if isinstance(robot_pose, Point2) or isinstance(robot_pose, Vector):
            assert robot_pose.dof() == 2
            return {"state": robot_pose}
        raise NotImplementedError(
            f"IdentityModel not implemented for pose with type {type(robot_pose)}."
        )

    def dim(self) -> int:
        return 1


class UrdfRobotModel(KinematicsModel):
    def __init__(self, urdf_path: str):
        self.drm_model = drm.DifferentiableRobotModel(urdf_path)

    def _postprocess_quaternion(self, quat):
        # Convert quaternion convention (DRM uses xyzw, Theseus uses wxyz)
        quat1 = torch.cat([quat[..., 3:], quat[..., :3]])

        # Normalize quaternions
        quat2 = quat1 / torch.linalg.norm(quat1)

        return quat2

    def forward_kinematics(self, joint_states: RobotModelInput) -> Dict[str, LieGroup]:
        """Computes forward kinematics
        Args:
            joint_states: Vector of all joint angles
        Outputs:
            Dictionary that maps link name to link pose
        """
        # Check input dimensions
        assert joint_states.shape[-1] == len(self.drm_model.get_joint_limits())

        # Compute forward kinematics for all links
        link_poses: Dict[str, LieGroup] = {}
        for link_name in self.drm_model.get_link_names():
            pos, quat = self.drm_model.compute_forward_kinematics(
                joint_states, link_name
            )
            quat_processed = self._postprocess_quaternion(quat)

            link_poses[link_name] = SE3(
                x_y_z_quaternion=torch.cat([pos, quat_processed], dim=-1)
            )

        return link_poses

    def dim(self) -> int:
        return len(self.drm_model.get_joint_limits())