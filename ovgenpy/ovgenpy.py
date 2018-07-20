# -*- coding: utf-8 -*-

import time
from pathlib import Path
from typing import NamedTuple, Optional, List

import click
from ovgenpy.channel import Channel

from ovgenpy.renderer import MatplotlibRenderer, RendererConfig
from ovgenpy.triggers import TriggerConfig, CorrelationTrigger
from ovgenpy.wave import WaveConfig, Wave


RENDER_PROFILING = True


class Config(NamedTuple):
    wave_dir: str
    master_wave: Optional[str]
    fps: int
    time_visible_ms: int
    scan_ratio: float

    trigger: TriggerConfig  # Maybe overriden per Wave
    render: RendererConfig

    @property
    def time_visible_s(self) -> float:
        return self.time_visible_ms / 1000


Folder = click.Path(exists=True, file_okay=False)
File = click.Path(exists=True, dir_okay=False)

_FPS = 60  # f_s


@click.command()
@click.argument('wave_dir', type=Folder)
@click.option('--master-wave', type=File, default=None)
@click.option('--fps', default=_FPS)
def main(wave_dir: str, master_wave: Optional[str], fps: int):
    cfg = Config(
        wave_dir=wave_dir,
        master_wave=master_wave,
        fps=fps,
        time_visible_ms=25,
        scan_ratio=1,

        trigger=CorrelationTrigger.Config(
            trigger_strength=10,
            use_edge_trigger=True,

            responsiveness=0.1,
            falloff_width=.5,
        ),
        render=RendererConfig(     # todo
            1280, 720,
            ncols=1
        )
    )

    ovgen = Ovgen(cfg)
    ovgen.write()


COLOR_CHANNELS = 3


class Ovgen:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.waves: List[Wave] = []
        self.channels: List[Channel] = []
        self.nchan: int = None

    def write(self):
        self._load_waves()  # self.waves =
        self._render()

    def _load_waves(self):
        wave_dir = Path(self.cfg.wave_dir)

        for idx, path in enumerate(wave_dir.glob('*.wav')):
            wcfg = WaveConfig(
                # fixme
            )

            wave = Wave(wcfg, str(path))
            self.waves.append(wave)

            trigger = self.cfg.trigger(
                wave=wave,
                scan_nsamp=round(
                    self.cfg.time_visible_s * self.cfg.scan_ratio * wave.smp_s),
                # I tried extracting variable, but got confused as a result
            )
            channel = Channel(None, wave, trigger)
            self.channels.append(channel)

        self.nchan = len(self.waves)

    def _render(self):
        # Calculate number of frames (TODO master file?)
        time_visible_s = self.cfg.time_visible_s
        fps = self.cfg.fps

        nframes = fps * self.waves[0].get_s()
        nframes = int(nframes) + 1

        renderer = MatplotlibRenderer(self.cfg.render, self.nchan)

        if RENDER_PROFILING:
            begin = time.perf_counter()

        # For each frame, render each wave
        for frame in range(nframes):
            time_seconds = frame / fps

            datas = []
            # Get data from each wave
            for wave, channel in zip(self.waves, self.channels):
                sample = round(wave.smp_s * time_seconds)
                region_len = round(wave.smp_s * time_visible_s)

                trigger_sample = channel.trigger.get_trigger(sample)
                datas.append(wave.get_around(trigger_sample, region_len))

            print(frame)
            renderer.render_frame(datas)

        if RENDER_PROFILING:
            # noinspection PyUnboundLocalVariable
            dtime = time.perf_counter() - begin
            render_fps = nframes / dtime
            print(f'FPS = {render_fps}')
