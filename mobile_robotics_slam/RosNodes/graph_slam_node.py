import rclpy
import os
import sys
import signal
from rclpy.node import Node
import matplotlib.pyplot as plt

import numpy as np
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
import time
import message_filters
from ament_index_python.packages import get_package_share_directory

try:
    package_share_dir = get_package_share_directory('mobile_robotics_slam')
    file_location_subfolders = 4 #Number of folder to go up to reach root of package
    for _ in range(file_location_subfolders):
        package_share_dir = os.path.dirname(package_share_dir)
    package_dir = os.path.join(package_share_dir, "mobile_robotics_slam")
    print("Package Directory: ", package_dir)
except:
    path = __file__
    file_location_subfolders = 3 #Number of folder to go up to reach root of package
    for _ in range(file_location_subfolders):
        path = os.path.dirname(path)
    package_dir = path
    sys.path.insert(0, package_dir)
    print("Package Directory: ", package_dir)



from mobile_robotics_slam.Extractors.Reflectors.ReflectorExtractor import ReflectorExtractor
from mobile_robotics_slam.Extractors.Corners.CornerExtractor import CornerExtractor
from mobile_robotics_slam.GraphHandler.g2oGraphHandler import GraphHandler as g2oGraphHandler
from mobile_robotics_slam.GraphHandler.GTSAMGraphHandler import GraphHandler as GTSAMGraphHandler
from mobile_robotics_slam.ICP.ICP_SVD import icp
from mobile_robotics_slam.MapGenerator.OnlineMap import DynamicMapUpdater
import mobile_robotics_slam.Params.simulation_params as params





class GraphSlamNode(Node):

##################################################################
# Initialization
##################################################################
    def __init__(self):
        super().__init__("graph_slam_node", parameter_overrides=[]) 

        # Declare variables
        self.OdomInitialPose = np.array([None, None, None])
        self.OdomLastNodePose = np.zeros(3)
        self.ICPLastNodePose = np.zeros(3)
        self.OptimizedLastNodePose = np.zeros(3)
        self.OptimizedLastNodeScan = None
        self.T_robot_laser = self.pose_to_transform(params.ROBOT_LASER_FRAME_OFFSET) # Set Laser frame position wrt Robot Frame (x,y, theta)
        self.T_laser_robot = np.linalg.inv(self.T_robot_laser)
        self.first_pose_added = False
        self.new_pose_added = False
        self.add_last_pose = False
        self.reflector_extractor = ReflectorExtractor()
        self.corner_extractor = CornerExtractor()
        self.setup_extractor_parameters()

        self.graph_handler = GTSAMGraphHandler()
        #self.graph_handler = g2oGraphHandler()

        self.real_trajectory = []
        self.odom_trajectory = []
        self.icp_trajectory = []


        self.dynamic_map = DynamicMapUpdater()
        self.dynamic_map.start()

        self.odom_sub = message_filters.Subscriber(self, Odometry, params.ODOM_TOPIC)
        self.scan_sub = message_filters.Subscriber(self, LaserScan, params.SCAN_TOPIC)
        self.real_pose_sub = message_filters.Subscriber(self, Odometry, params.REAL_POSE_TOPIC)
        self.map_update_timer = self.create_timer(3, self.map_timer_callback)

        # Approximate time synchronizer
        self.sync = message_filters.ApproximateTimeSynchronizer(
            [self.odom_sub, self.scan_sub, self.real_pose_sub], 
            queue_size=30, 
            slop=0.0001 #Max difference between timestamps
        )
        self.sync.registerCallback(self.synchronized_callback)


    def setup_extractor_parameters(self):
        # Set the parameters of the Corner Extractor
        min_corner_angle = params.MIN_CORNER_ANGLE
        max_corner_angle = params.MAX_CORNER_ANGLE
        max_intersecton_distance = params.MAX_INTERSECTION_DISTANCE
        self.corner_extractor.set_corner_params(max_intersecton_distance, min_corner_angle, max_corner_angle)

        # Set the parameters of the Adaptive Segment Detector
        sigma_ranges = params.SIGMA_RANGES
        lambda_angle = params.LAMBDA_ANGLE
        merge_distance = params.MERGE_DISTANCE
        min_points_density = params.MIN_POINT_DENSITY
        min_segment_length = params.MIN_SEGMENT_LENGTH
        self.corner_extractor.set_detector_params(sigma_ranges, lambda_angle, merge_distance, min_points_density, min_segment_length)

        # Set the parameters of the Segment Handler
        epsilon = params.EPSILON
        min_density_after_segmentation = params.MIN_DENSITY_AFTER_SEGMENTATION
        min_length_after_segmentation = params.MIN_LENGTH_AFTER_SEGMENTATION
        self.corner_extractor.set_handler_params(epsilon, min_density_after_segmentation, min_length_after_segmentation)

    def map_timer_callback(self):
        if not self.new_pose_added:
            return
        poses, pointclouds, landmarks = self.graph_handler.get_optimized_poses_and_landmarks()
        cartesian_points = []
        robot_poses = []
        
        for pose, pointcloud in zip(poses, pointclouds):

            distance_mask = pointcloud<params.MAP_SCAN_DISTANCE_THRESHOLD
            angle = np.linspace(-np.pi, np.pi, len(pointcloud))
            x = pose[0] + pointcloud * np.cos(angle + pose[2])
            y = pose[1] + pointcloud * np.sin(angle + pose[2])
            cartesian_points.extend(np.vstack((x[distance_mask], y[distance_mask])).T)
            # In poses there is laser pose, we need to convert it to robot pose
            robot_poses.append(self.transform_to_pose(self.pose_to_transform(pose)@self.T_laser_robot))
        
        self.dynamic_map.add_data(robot_poses, landmarks, cartesian_points)
        self.new_pose_added = False


    def compute_homo_transform(self, pose1, pose2):
        """
            Given two poses (x,y,theta) return the homogeneous transformation between them
            Input:  pose1: (x,y,theta) of previous pose
                    pose2: (x,y,theta) of new pose
            
            Output: H: Homogeneous transformation between the two poses (3x3 matrix)
                    distance: linear distance between the two poses 
                    rotation: angular rotation between two poses
        """
        T1 = self.pose_to_transform(pose1)
        T2 = self.pose_to_transform(pose2)
        H = np.linalg.inv(T1)@T2
        distance = np.linalg.norm(H[0:2, 2])
        rotation = np.abs(np.arctan2(H[1,0], H[0,0]))

        return H, distance, rotation

    def pose_to_transform(self, pose):
        """Given a pose [x,y,theta] it returns the Homogeneous with respect to origin (0,0,0)
        transform T of the pose"""
        cos = np.cos(pose[2])
        sin = np.sin(pose[2])
        dx = pose[0]
        dy = pose[1]
        T = np.array([[cos, -sin, dx],
                      [sin, cos , dy],
                      [0  , 0   , 1 ]])
        return T
    
    def transform_to_pose(self, T):
        """Given a Homogeneous Transform T it returns the pose [x,y,theta]"""
        theta = np.arctan2(T[1,0], T[0,0])
        x = T[0, 2]
        y = T[1, 2]
        return np.array([x,y,theta])
    
    def add_first_pose(self, odom: Odometry, scan: LaserScan, real: Odometry):
        """Add the first pose to the graph"""
        self.OdomReference = np.array([odom.pose.pose.position.x, odom.pose.pose.position.y, self.quaternion_to_euler(odom.pose.pose.orientation.x,odom.pose.pose.orientation.y,odom.pose.pose.orientation.z,odom.pose.pose.orientation.w)])
        self.OdomLastNodePose = np.zeros(3) # Initialize First Pose as origin (0,0,0)
        self.ICPLastNodePose = np.zeros(3) # Initialize First Pose as origin (0,0,0)
        self.OptimizedLastNodePose = np.zeros(3) # Initialize First Pose as origin (0,0,0)
        self.OptimizedLastNodeScan = np.array(scan.ranges)
        laser_estimated_pose = self.transform_to_pose(self.T_robot_laser) # Initialize Laser Pose as Laser Frame wrt Robot Frame
        self.odom_trajectory.append(np.copy(self.OdomLastNodePose))
        self.real_trajectory.append(np.array([real.pose.pose.position.x, real.pose.pose.position.y, self.quaternion_to_euler(real.pose.pose.orientation.x,real.pose.pose.orientation.y,real.pose.pose.orientation.z,real.pose.pose.orientation.w)]))
        self.icp_trajectory.append(np.copy(self.OdomLastNodePose))
        reflectors = []
        corners = []
        if params.EXTRACT_CORNER:
            corners = self.extract_corners(scan, laser_estimated_pose)
        if params.EXTRACT_REFLECTORS:
            reflectors = self.extract_reflectors(scan, laser_estimated_pose)
        landmarks = reflectors + corners
        laser_optimized_pose = self.graph_handler.add_to_graph(laser_estimated_pose, np.array(scan.ranges), landmarks)
        T_laser_optimized = self.pose_to_transform(laser_optimized_pose)
        self.OptimizedLastNodePose = self.transform_to_pose(T_laser_optimized@self.T_laser_robot)
        self.new_pose_added = True


    def synchronized_callback(self, odom: Odometry, scan: LaserScan, real: Odometry):
        start_time = time.time()
        if not self.first_pose_added:
            self.add_first_pose(odom, scan, real)
            self.first_pose_added = True
            return
        
        real_pose = np.array([real.pose.pose.position.x, real.pose.pose.position.y, self.quaternion_to_euler(real.pose.pose.orientation.x,real.pose.pose.orientation.y,real.pose.pose.orientation.z,real.pose.pose.orientation.w)])
        odom_pose = np.array([odom.pose.pose.position.x, odom.pose.pose.position.y, self.quaternion_to_euler(odom.pose.pose.orientation.x,odom.pose.pose.orientation.y,odom.pose.pose.orientation.z,odom.pose.pose.orientation.w)])
         
        #Estimate Motion of Robot Using Odometry
        H_robot_odom, travel_distance, rotation = self.compute_homo_transform(self.OdomReference, odom_pose)
        
        #If Motion Higher than THRESHOLD correct it using ICP
        if travel_distance > params.DISTANCE_THRESHOLD or rotation > params.ROTATION_THRESHOLD or self.add_last_pose:
            
            #ICP is WRT Laser Frame so converti H_robot into H_laser
            H_laser_odom = self.T_laser_robot@H_robot_odom@self.T_robot_laser # Homogeneous Transform of LASER due to Odometry estimate)

            #Prepare previous and current scan for ICP
            angles = np.linspace(scan.angle_min, scan.angle_max, len(scan.ranges))
            cos = np.cos(angles)
            sin = np.sin(angles)
            previous_scan = np.copy(self.OptimizedLastNodeScan)
            current_scan = np.array(scan.ranges)
            current_points = np.vstack((current_scan*cos, current_scan*sin)).T
            previous_points = np.vstack((previous_scan*cos, previous_scan*sin)).T

            #Perform ICP to estimate a better H_laser and thus H_robot
            H_laser_icp = icp(current_points, previous_points, init_transform=H_laser_odom, downsample=4, max_iterations=30, max_range=15)
            H_robot_icp = self.T_robot_laser@H_laser_icp@self.T_laser_robot

            #Update the estimated pose of the laser given the ICP result
            Tr = self.pose_to_transform(self.OptimizedLastNodePose)
            laser_estimated_pose = self.transform_to_pose((Tr@H_robot_icp)@self.T_robot_laser)
                
            #Extract Landmarks from the scan wrt Laser Frame
            reflectors = []
            corners = []
            if params.EXTRACT_CORNER:
                corners = self.extract_corners(scan, laser_estimated_pose)
            if params.EXTRACT_REFLECTORS:
                reflectors = self.extract_reflectors(scan, laser_estimated_pose)
            landmarks = reflectors + corners
            
            #Add the estimated of laser pose to the graph and get the optimized pose of laser
            laser_optimized_pose = self.graph_handler.add_to_graph(laser_estimated_pose, np.array(scan.ranges), landmarks)
            T_laser_optimized = self.pose_to_transform(laser_optimized_pose)

            #Update the optimized pose of the robot given the optimized pose of the laser
            self.OptimizedLastNodePose = self.transform_to_pose(T_laser_optimized@self.T_laser_robot)
            
            #Store Data about the Node for the next iteration
            Tr_odom = self.pose_to_transform(self.OdomLastNodePose)
            Tr_ICP = self.pose_to_transform(self.ICPLastNodePose)
            self.OdomLastNodePose = self.transform_to_pose(Tr_odom@H_robot_odom)
            self.ICPLastNodePose = self.transform_to_pose(Tr_ICP@H_robot_icp)
            self.OdomReference = np.copy(odom_pose)
            self.OptimizedLastNodeScan = np.copy(scan.ranges)

            #Store Data for Visualization
            self.odom_trajectory.append(np.copy(self.OdomLastNodePose))
            self.real_trajectory.append(np.copy(real_pose))
            self.icp_trajectory.append(np.copy(self.ICPLastNodePose))

            self.new_pose_added = True
            

            print("\n\nTime For Processing: ", time.time() - start_time)
            print(f"Odom Estimate: {self.OdomLastNodePose}")      
            print(f"Estimated Pose: {self.OptimizedLastNodePose}")
            print(f"Real Pose: {real_pose}")

            if self.add_last_pose:
                print("Last Pose Added")
                self.add_last_pose = False
                self.save_data()
    
    def save_data(self):
        poses, _, landmarks = self.graph_handler.get_optimized_poses_and_landmarks()
        robot_trajectory = []
        for pose in poses:
            robot_trajectory.append(self.transform_to_pose(self.pose_to_transform(pose)@self.T_laser_robot))
        robot_trajectory = np.array(robot_trajectory)
        
        # If directory does not exist, create it
        save_path = os.path.join(package_dir, "trajectory_data")
        if not os.path.exists(save_path):
            os.makedirs(save_path)

        # Save the data
        np.savetxt(os.path.join(save_path, "robot_optimized.txt"), robot_trajectory)
        np.savetxt(os.path.join(save_path,  "real_trajectory.txt"), np.array(self.real_trajectory))
        np.savetxt(os.path.join(save_path,  "odom_trajectory.txt"), np.array(self.odom_trajectory))
        np.savetxt(os.path.join(save_path,  "icp_trajectory.txt"), np.array(self.icp_trajectory))
        np.savetxt(os.path.join(save_path,  "landmarks.txt"), np.array(landmarks))

        print(f"Saved Data in Folder: {save_path} ")
                       

    def extract_reflectors(self, scan: LaserScan, scan_frame_pose):
        """Extracts the reflectors from the scan and returns them as keypoints
            Input:  scan: LaserScan message
                    scan_frame_pose: Pose of the laser frame in global coordinates
            Output: keypoints: list of reflectors keypoint as Object with global position
        """
        pointcloud = np.array(scan.ranges)
        intensities = np.array(scan.intensities)
        field_of_view = scan.angle_max - scan.angle_min
        angle_min = scan.angle_min
        self.reflector_extractor.extract_reflectors(pointcloud, intensities, field_of_view, angle_min, scan_frame_pose)
        keypoints = self.reflector_extractor.get_reflectors()
        return keypoints


    def extract_corners(self, scan: LaserScan, scan_frame_pose):
        """Extracts the corners from the scan and returns them as keypoints
            Input:  scan: LaserScan message
                    scan_frame_pose: Pose of the laser frame in global coordinates
            Output: keypoints: list of corners keypoint as Object with global position
        """
        pointcloud = np.array(scan.ranges)
        field_of_view = scan.angle_max - scan.angle_min
        angle_min = scan.angle_min
        self.corner_extractor.extract_corners(pointcloud, field_of_view, angle_min, scan_frame_pose)
        keypoints = self.corner_extractor.get_corners()
        return keypoints
        

    def quaternion_to_euler(self, x, y, z, w):
        """Converts quaternion to euler angles"""
        phi = np.arctan2(2.0 * (w * z + x * y), w * w + x * x - y * y - z * z)
        return phi
    
    def euler_to_quaternion(self, phi):
        """Converts euler angles to quaternion"""
        x = 0.0
        y = 0.0
        z = np.sin(phi / 2)
        w = np.cos(phi / 2)
        return x, y, z, w
    
    def polar_to_cartesian(self, range, angle):
        """Converts polar coordinates to cartesian
        Input:  range: distance to the object
                angle: angle to the object
                Output: array with x and y coordinates"""
        x = range * np.cos(angle)
        y = range * np.sin(angle)
        return np.array([x, y])
    
    def cartesian_to_polar(self, x, y):
        """Converts cartesian coordinates to polar
        Input:  x: x coordinate
                y: y coordinate
                Output: array with range and angle"""
        range = np.sqrt(x**2 + y**2)
        angle = np.arctan2(y, x)
        return np.array([range, angle])
    
    def signal_handler(self,sig, frame):
        self.add_last_pose = True    
    

def main(args=None):
    rclpy.init(args=args)

    print("SLAM node started")

    slam_node = GraphSlamNode()
    signal.signal(signal.SIGINT, slam_node.signal_handler)
    try:
        rclpy.spin(slam_node)
    except Exception as e:
        print("Shutting down graph slam node.")
    finally:
        slam_node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

