import numpy as np

#### START GRAPH SLAM PARAMETERS ####
DISTANCE_THRESHOLD = 0.2  # Distance threshold to create a new node
ROTATION_THRESHOLD = np.deg2rad(3) # Rotation threshold to create a new node
EXTRACT_CORNER = True  # Extract corners from the scan
EXTRACT_REFLECTORS = False   # Extract reflectors from the scan
ROBOT_LASER_FRAME_OFFSET = [-0.109, 0, 0]  # Offset (x, y, theta) From Robot frame to laser frame
ODOM_TOPIC = "/odometry/filtered"  # Topic where the scan is published
SCAN_TOPIC = "/scan"  # Topic where the odometry is published
REAL_POSE_TOPIC = "/odometry/filtered"  # Topic where the real pose is published
MAP_SCAN_DISTANCE_THRESHOLD = 6 # Maximum Range of the scan points to add them to the map
#### START GRAPH SLAM PARAMETERS ####

#### START REFLECTOR EXTRACTOR PARAMETERS ####
MIN_REFLECTOR_POINTS = 4 # Minimum number of points to consider a reflector
MIN_REFLECTOR_RADIUS = 0.02 # Minimum radius of a reflector
MAX_REFLECTOR_RADIUS = 0.15 # Maximum radius of a reflector
MIN_REFLECTOR_INTENSITY = 1000 # Minimum intensity of a reflector
CLUSTER_RADIUS = 0.8 # Maximum distance between two reflectors to consider them as part of the same cluster
MAX_RANGE_EXTRACTION = 30 # Maximum range of the reflectors
MIN_RANGE_EXTRACTION = 0.01 # Minimum range of the reflectors
#### END REFLECTOR EXTRACTOR PARAMETERS ####

#### START CORNER EXTRACTOR PARAMETERS ####
MIN_CORNER_ANGLE = 85 # Minimum angle between two segments to consider their intersecttion as a corner
MAX_CORNER_ANGLE = 95 # Maximum angle between two segments to consider their intersecttion as a corner
MAX_INTERSECTION_DISTANCE = 0.4 # Maximum distance between the intersection point and the segments to consider it as a corner

# Set the parameters of the Adaptive Segment Detector
SIGMA_RANGES = 0.2 # Standard deviation of the Gaussian kernel for the range
LAMBDA_ANGLE = 10   # Parameter of the Adaptive Segment Detector
MERGE_DISTANCE = 0.07 # Maximum distance between two segments endpoints to merge them
MIN_POINT_DENSITY = 5 # Minimum number of points to consider a segment
MIN_SEGMENT_LENGTH = 0.2 # Minimum length of a segment to be considered

# Set the parameters of the Segment Handler
EPSILON = 0.12 # Minimum distance between Line and a point to determine if the point is on the line
MIN_DENSITY_AFTER_SEGMENTATION = 8 # Minimum number of points to consider a segment after segmentation
MIN_LENGTH_AFTER_SEGMENTATION = 0.3 # Minimum length of a segment to be considered after segmentation
#### END CORNER EXTRACTOR PARAMETERS ####

#### START CORNER MATCHING PARAMETERS ####
CORNER_RELATIVE_DISTANCE_TOLERANCE = 0.06 # Relative distance between two pairs of compatible corners to add and edge in the compatibility graph
CORNER_RELATIVE_ANGLE_TOLERANCE = 3 # Relative angle between two pairs of compatible corners to add and edge in the compatibility graph
CORNER_NEIGHBOR_MAX_DISTANCE = 0.3 # Maximum distance between mapped and extracted corners to consider them as possible matches
CORNER_ADD_DISTANCE_THRESHOLD = 0.1 # Minimum distance between a new corner and existing corners to add it to the map
#### END CORNER MATCHING PARAMETERS ####

#### START REFLECTOR MATCHING PARAMETERS ####
REFLECTOR_RELATIVE_DISTANCE_TOLERANCE = 0.03 # Relative distance between two pairs of compatible reflectors to add and edge in the compatibility graph
REFLECTOR_NEIGHBOR_MAX_DISTANCE = 2 # Maximum distance between mapped and extracted reflectors to consider them as possible matches
REFLECTOR_ADD_DISTANCE_THRESHOLD = 1.5  # Minimum distance between a new reflector and existing reflectors to add it to the map
#### END REFLECTOR MATCHING PARAMETERS ####



