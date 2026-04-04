# =============================================================================
# Stage 1 — Build micro-ROS agent from source
# =============================================================================
FROM ros:jazzy-ros-base AS builder

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    python3-colcon-common-extensions \
    python3-colcon-mixin \
    python3-vcstool \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ws/src

# Clone micro-ROS agent and its message definitions
RUN git clone --depth 1 -b jazzy \
        https://github.com/micro-ROS/micro-ROS-Agent.git && \
    git clone --depth 1 -b jazzy \
        https://github.com/micro-ROS/micro_ros_msgs.git

WORKDIR /ws

# Build in Release mode with link-time optimisation for maximum performance
RUN . /opt/ros/jazzy/setup.sh && \
    colcon build \
        --cmake-args \
            -DCMAKE_BUILD_TYPE=Release \
            -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=ON \
        --no-warn-unused-cli \
        --event-handlers console_cohesion+

# =============================================================================
# Stage 2 — Minimal runtime image
# =============================================================================
FROM ros:jazzy-ros-base

ARG DEBIAN_FRONTEND=noninteractive

# Runtime deps only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-jazzy-rmw-fastrtps-cpp \
    && rm -rf /var/lib/apt/lists/*

# Copy compiled install tree from the builder stage
COPY --from=builder /ws/install /ws/install

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# UDP port used by the micro-XRCE-DDS transport
EXPOSE 8888/udp

ENTRYPOINT ["/entrypoint.sh"]

# Default: listen on UDP port 8888 with verbose logging
# Override via docker-compose command: or docker run args
CMD ["udp4", "--port", "8888", "-v6"]
