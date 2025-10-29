BASE=$(pwd)
TESTS=${BASE}/Matrix-tests
LINUX=${BASE}/linux-kernel
NEMU=${BASE}/NEMU-Matrix

M=0
N=0
L=0
R=0

while getopts "mnlr" OPT; do
    case $OPT in
        m) M=1;;
        n) N=1;;
        l) L=1;;
        r) R=1;;
        \?)
            echo "Unknown option: -$OPT"
            echo "Usage: $0 [-m] [-n] [-l] [-r]"
            echo "  -m: build matrix workload"
            echo "  -n: build NEMU"
            echo "  -l: build linux kernel"
            echo "  -r: run workload on NEMU"
            exit 1
            ;;
    esac
done

if [ $M -eq 1 ] && [ $L -eq 0 ]; then
    echo "Warning: -m requires -l. Automatically enabling -n."
    N=1
fi

if [ $M -eq 1 ]; then
    echo "********** build matrix workload **********"
    cd ${TESTS}
    ./compiler.sh ./isa/xiangshan_mul_full.c
    cd ${BASE}
fi

if [ $N -eq 1 ]; then
    echo "********** build NEMU **********"
    # make -C ${NEMU} riscv64-matrix-xs_defconfig
    make -C ${NEMU} -j64
fi

# if [ ??? -eq 1 ]; then
    # echo "********** build workloads in rootfs **********"
    # make -C ${LINUX}/riscv-rootfs -j64
# fi

if [ $L -eq 1 ]; then
    echo "********** build linux kernel **********"
    rm ${LINUX}/linux-6.10.3/vmlinux.o
    make -C ${LINUX}/linux-6.10.3 -j64

    echo "********** build opensbi **********"
    make -C ${LINUX}/opensbi PLATFORM=generic FW_PAYLOAD_PATH=$RISCV_LINUX_HOME/arch/riscv/boot/Image FW_FDT_PATH=$WORKLOAD_BUILD_ENV_HOME/dts/build/xiangshan.dtb FW_PAYLOAD_OFFSET=0x200000 -j64
fi

if [ $R -eq 1 ]; then
    echo "********** run workload on NEMU **********"
    ${NEMU}/build/riscv64-nemu-interpreter -b ${LINUX}/opensbi/build/platform/generic/firmware/fw_payload.bin 1> ${NEMU}/seesee5.txt 2> ${NEMU}/stderr.txt
    echo "Done"

    cd ${NEMU} && python3 addr.py && cd ${BASE}
    echo "addr.py parse"
fi

