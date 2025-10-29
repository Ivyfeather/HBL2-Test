#set -x
export LINUX=linux-kernel
export RISCV_LINUX_HOME=$(pwd)/${LINUX}/linux-6.10.3
export RISCV_ROOTFS_HOME=$(pwd)/${LINUX}/riscv-rootfs
export WORKLOAD_BUILD_ENV_HOME=$(pwd)/${LINUX}/nemu_board
export OPENSBI_HOME=$(pwd)/${LINUX}/opensbi
export RISCV=/nfs/home/share/riscv # consider use llvm-stc with M-ext?

export ARCH=riscv
export CROSS_COMPILE=$RISCV/bin/riscv64-unknown-linux-gnu-
export NEMU_HOME=$(pwd)/NEMU-Matrix

# for verilator simluation
ulimit -s 16384
