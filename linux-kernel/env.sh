#set -x
export RISCV_LINUX_HOME=$(pwd)/linux-6.10.3
export RISCV_ROOTFS_HOME=$(pwd)/riscv-rootfs
export WORKLOAD_BUILD_ENV_HOME=$(pwd)/nemu_board
export OPENSBI_HOME=$(pwd)/opensbi
export RISCV=/nfs/home/share/riscv # consider use llvm-stc with M-ext?

export ARCH=riscv
export CROSS_COMPILE=$RISCV/bin/riscv64-unknown-linux-gnu-
