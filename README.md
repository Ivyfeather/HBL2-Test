# HBL2-Test
Test Framework for HBL2 (High Bandwidth L2 Cache)

## Overview
This repository contains the test framework for HBL2, including tools for trace generation and hardware simulation.

## Submodules

### NEMU-Matrix
- **Repository**: https://github.com/cailuoshan/NEMU-Matrix.git
- **Purpose**: Used to generate execution traces for testing

### tl-test-new
- **Repository**: https://github.com/OpenXiangShan/tl-test-new.git
- **Purpose**: Uses traces from NEMU to run HBL2 hardware simulation

## Getting Started

### Clone with Submodules
```bash
git clone --recursive https://github.com/Ivyfeather/HBL2-Test.git
```

### Initialize Submodules (if already cloned)
```bash
git submodule update --init --recursive
```

## Workflow
1. Use NEMU-Matrix to generate execution traces
2. Feed the generated traces to tl-test-new for HBL2 hardware simulation
