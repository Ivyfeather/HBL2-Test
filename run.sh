BASE=$(pwd)
TESTS=${BASE}/Matrix-tests
LINUX=${BASE}/linux-kernel
NEMU=${BASE}/NEMU-Matrix
TLTEST=${BASE}/tl-test-new-matrix

THREADS_BUILD=${THREADS_BUILD:-$(($(nproc)/2))}
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
            echo "Usage: $0 [-m/n/l/r/c/t]"
            echo "  -m: build matrix workload"
            echo "  -n: build NEMU"
            echo "  -l: build linux kernel"
            echo "  -r: run workload on NEMU"
	    echo "  -c: RTL and verilator compilation"
	    echo "  -t: tl-test compilation and run"
            exit 1
            ;;
    esac
done

if [ $M -eq 1 ] && [ $L -eq 0 ]; then
    echo "Warning: -m requires -l. Automatically enabling -l."
    L=1
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
    make -C ${NEMU} -j${THREADS_BUILD}
fi

# if [ ??? -eq 1 ]; then
    # echo "********** build workloads in rootfs **********"
    # make -C ${LINUX}/riscv-rootfs -j${THREADS_BUILD}
# fi

if [ $L -eq 1 ]; then
    # make -C ${LINUX}/linux-6.10.3 clean -j${THREADS_BUILD}
    # make -C ${LINUX}/linux-6.10.3 xiangshan_defconfig -j${THREADS_BUILD}

    echo "********** build linux kernel **********"
    rm ${LINUX}/linux-6.10.3/vmlinux.o
    make -C ${LINUX}/linux-6.10.3 -j${THREADS_BUILD}

    echo "********** build opensbi **********"
    make -C ${LINUX}/opensbi PLATFORM=generic FW_PAYLOAD_PATH=$RISCV_LINUX_HOME/arch/riscv/boot/Image FW_FDT_PATH=$WORKLOAD_BUILD_ENV_HOME/dts/build/xiangshan.dtb FW_PAYLOAD_OFFSET=0x200000 -j${THREADS_BUILD}
fi

if [ $R -eq 1 ]; then
    echo "********** run workload on NEMU **********"
    ${NEMU}/build/riscv64-nemu-interpreter -b ${LINUX}/opensbi/build/platform/generic/firmware/fw_payload.bin 1> ${NEMU}/stdout.txt 2> ${NEMU}/stderr.txt
    echo "Done"

    cd ${NEMU} && python3 addr.py && cd ${BASE}
    echo "addr.py parse"

    cp ${NEMU}/line_trace.txt ${TLTEST}
fi

