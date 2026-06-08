# Radar Nexys Video 当前可运行版本复刻指南

更新时间：2026-03-31

## 1. 这份文档是干什么的

这份文档专门回答一个实际问题：

> 如果以后要在另一台机器上，或者在未来某个时间点，把“当前这个已经跑通的版本”重新拉起来，应该怎么做？

这里说的“当前这个已经跑通的版本”指的是：

- `Rocket CPU + DDR + AXI interconnect + AXI DMA`
- 在 Nexys Video 板上已经完成端到端 loopback 验证
- 顶层仓库与相关子模块修改都已经保存到你自己的 GitHub 仓库体系中

本文不展开 debug 过程，只讲“如何正确复刻”。

---

## 2. 先理解仓库结构

### 2.1 为什么你会看到多个 GitHub 仓库

当前这套工程不是只有一个仓库，而是“一个主仓库 + 多个子模块仓库”的结构。

#### 主仓库

- `Lazyguy524/radar_chipyard`

这个仓库是总工程仓库，负责保存：

- 顶层 Chipyard 工程代码
- 你的测试程序
- 当前中文文档
- 当前 HTML 架构说明
- 以及“各个子模块应该指向哪个 commit”

#### 当前和本项目直接相关的子模块 fork

- `Lazyguy524/rocket-chip-fpga-shells`
- `Lazyguy524/testchipip`
- `Lazyguy524/spike-devices`

这些仓库不是多余的副本，而是当前工程真正依赖的外部组件 fork。  
因为这次 bring-up 过程中，除了主仓库本身之外，还修改了这些子模块里的代码，所以必须把它们也保存到你自己的 GitHub 账号下。

### 2.2 可以怎么理解这几个仓库的关系

最简单的理解方式是：

- `radar_chipyard` 是整车
- `rocket-chip-fpga-shells` / `testchipip` / `spike-devices` 是你这辆车上换过的零件

主仓库不会把这些子模块的全部内容重新复制一份进去，它只会记录：

- 应该使用哪个子模块仓库
- 应该停在哪个 commit

所以以后复刻时，不能只 clone 主仓库然后忽略 submodule；  
必须把子模块一起同步下来。

---

## 3. 当前已经保存到 GitHub 的内容

截至现在，GitHub 上已经有以下内容：

### 3.1 主仓库分支

主仓库：

- `Lazyguy524/radar_chipyard`

当前保存本次工作结果的分支：

- `radar-nexysvideo-backup-2026-03-26`

这个分支里已经包含：

- 当前中文系统整理文档
- 当前复刻文档
- 当前 HTML 架构说明
- 当前测试程序
- 当前最小 bring-up runtime
- 当前 `.gitmodules`
- 以及与当前状态匹配的 submodule pointer

### 3.2 子模块分支

当前三个关键子模块也已经推到了你自己的 fork 中。

#### `rocket-chip-fpga-shells`

仓库：

- `Lazyguy524/rocket-chip-fpga-shells`

分支：

- `radar-nexysvideo-mig-idwidth-fix`

作用：

- 保存 Nexys Video MIG wrapper 的 AXI ID 宽度修复

#### `testchipip`

仓库：

- `Lazyguy524/testchipip`

分支：

- `radar-nexysvideo-uart-tsi-stale-byte-fix`

作用：

- 保存 `uart_tsi` 对 stale 串口字节的处理修复

#### `spike-devices`

仓库：

- `Lazyguy524/spike-devices`

分支：

- `radar-nexysvideo-fdt-include-fix`

作用：

- 保存本地构建所需的 `fdt` include path 修复

---

## 4. 最标准的复刻方法

这是以后最推荐的做法。

### 4.1 直接 clone 你的主仓库分支

在新机器上执行：

```bash
git clone --recursive -b radar-nexysvideo-backup-2026-03-26 git@github.com:Lazyguy524/radar_chipyard.git
```

这条命令的含义是：

- clone 主仓库
- 切到当前保存好的工作分支
- 同时递归拉取子模块

### 4.2 如果你已经 clone 过主仓库

如果某台机器上已经有仓库目录，那就进入目录后执行：

```bash
git checkout radar-nexysvideo-backup-2026-03-26
git pull
git submodule sync --recursive
git submodule update --init --recursive
```

这四步的意义是：

1. 切到正确的主分支
2. 拉取主仓库最新内容
3. 把本地 submodule URL 同步成 `.gitmodules` 中记录的 URL
4. 按当前 pointer 把子模块更新到正确 commit

### 4.3 为什么 `git submodule sync` 很重要

因为这次我们已经把几个关键子模块从“上游 URL”切换成了“你自己 GitHub 账号下的 fork URL”。

如果一台机器以前 clone 过旧版本，而它本地 `.git/config` 里还记着旧的 submodule URL，那么：

- 它可能还会继续去上游仓库拉
- 导致拉不到你当前这次保存的 commit

所以：

```bash
git submodule sync --recursive
```

这一步不要省。

---

## 5. 复刻后应该验证什么

仓库拉下来只是第一步，后面还要确认拉到的是“真正能工作的那套状态”。

建议按下面顺序检查。

### 5.1 检查主仓库分支

```bash
git branch --show-current
```

应该看到：

```bash
radar-nexysvideo-backup-2026-03-26
```

### 5.2 检查关键子模块 URL

```bash
git config -f .git/config --get submodule.fpga/fpga-shells.url
git config -f .git/config --get submodule.generators/testchipip.url
git config -f .git/config --get submodule.toolchains/riscv-tools/riscv-spike-devices.url
```

应该分别看到：

```bash
git@github.com:Lazyguy524/rocket-chip-fpga-shells.git
git@github.com:Lazyguy524/testchipip.git
git@github.com:Lazyguy524/spike-devices.git
```

### 5.3 检查关键子模块 commit

```bash
git -C fpga/fpga-shells rev-parse HEAD
git -C generators/testchipip rev-parse HEAD
git -C toolchains/riscv-tools/riscv-spike-devices rev-parse HEAD
```

如果你是按当前主仓库这套 pointer 正常更新下来的，那么它们会停在与当前已保存版本一致的 commit 上。

### 5.4 检查关键文档是否存在

建议确认这些文件都在：

- `docs/radar_nexysvideo_current_system_guide_2026-03-31.md`
- `docs/radar_nexysvideo_reproduction_guide_2026-03-31.md`
- `docs/radar_nexysvideo_system_arch.html`
- `tests/radar-axi-dma-loopback.c`
- `tests/radar-axi-dma-loopback-cachemaint.c`

---

## 6. 当前“可运行版本”的关键组成

以后如果你想判断“某次 clone 出来的版本是不是就是当前这个已跑通版本”，可以重点盯以下内容。

### 6.1 顶层仓库中必须存在的内容

- 当前中文说明文档
- 当前 HTML 架构说明
- `radar-axi-mmio-smoke.c`
- `radar-axi-dma-loopback.c`
- `radar-axi-dma-loopback-cacheprobe.c`
- `radar-axi-dma-loopback-cachemaint.c`
- `htif_crt0.S`
- `htif_nolib.c`

### 6.2 `rocket-chip-fpga-shells` 中必须存在的修复

必须包含：

- Nexys Video MIG wrapper 的 AXI ID 宽度修复
- 与当前 bring-up 相关的 MIG debug 导出

### 6.3 `testchipip` 中必须存在的修复

必须包含：

- `uart_tsi` 启动前对 stale UART bytes 的处理

### 6.4 `spike-devices` 中必须存在的修复

必须包含：

- `fdt` include path 的补充

---

## 7. 如果只 clone 主仓库，不更新子模块，会发生什么

这是一个很常见的坑。

如果你只执行：

```bash
git clone git@github.com:Lazyguy524/radar_chipyard.git
```

但没有执行：

```bash
git submodule update --init --recursive
```

那么你会遇到的问题包括：

- 子模块目录可能是空的
- 或者虽然目录在，但版本不是当前需要的 commit
- 或者 URL 仍然指向上游仓库而不是你的 fork

最终结果就是：

- 看起来主仓库文件都在
- 但真正构建时用到的关键代码并不是你这次保存下来的版本

所以一定要记住：

> 复刻这个项目时，submodule 不是可选项，而是主工程的一部分。

---

## 8. 如果以后你继续改这个项目，该怎么做

### 8.1 只改主仓库内容

如果以后你只改：

- 测试程序
- 文档
- 顶层 harness
- 主仓库内的 Scala/Chisel 集成逻辑

那么正常在主仓库里：

```bash
git add ...
git commit ...
git push
```

就可以。

### 8.2 改到了子模块内容

如果你改到了这些目录：

- `fpga/fpga-shells`
- `generators/testchipip`
- `toolchains/riscv-tools/riscv-spike-devices`

那就不能只推主仓库。

正确顺序是：

1. 先进入对应子模块目录提交并推送
2. 回到主仓库
3. 把新的 submodule pointer 提交并推送

也就是说，子模块修改永远是“两段式”：

- 先推子模块仓库
- 再推主仓库记录

---

## 9. 当前最建议保存的使用习惯

以后为了避免版本再混乱，建议固定以下习惯。

### 9.1 每次重要状态都记录主仓库分支名

当前已经工作的主分支是：

- `radar-nexysvideo-backup-2026-03-26`

以后每次进入新的稳定里程碑，建议再打新分支或 tag。

### 9.2 每次子模块改动后都立即推送

不要让子模块长期停留在“本地改过但 GitHub 上没有”的状态。

否则以后主仓库虽然记录了一个 pointer，但远端根本没有那个 commit，别人就复刻不出来。

### 9.3 每次切换机器后都先执行这两条

```bash
git submodule sync --recursive
git submodule update --init --recursive
```

这是最省事也最不容易踩坑的做法。

---

## 10. 最简复刻命令清单

如果你以后只想看最短步骤，记这一段就够了。

### 全新机器

```bash
git clone --recursive -b radar-nexysvideo-backup-2026-03-26 git@github.com:Lazyguy524/radar_chipyard.git
cd radar_chipyard
git submodule sync --recursive
git submodule update --init --recursive
```

### 旧机器已有仓库

```bash
git checkout radar-nexysvideo-backup-2026-03-26
git pull
git submodule sync --recursive
git submodule update --init --recursive
```

---

## 11. 总结

以后如果你要复刻当前这个已经跑通的版本，核心不是“记住很多零散操作”，而是记住下面三句话：

1. 当前真正的工程不只是 `radar_chipyard` 一个仓库，而是“主仓库 + 子模块 fork”的组合。
2. 复刻时一定要同步 submodule，并且先执行 `git submodule sync --recursive`。
3. 如果后续继续修改子模块，必须先推子模块，再推主仓库 pointer。

只要遵守这三条，当前这套已经打通的 Nexys Video 工程状态就可以稳定复刻下来。
