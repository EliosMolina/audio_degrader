import os
import librosa as lr
import logging
import numpy as np
from BaseDegradation import Degradation


class DegradationMix(Degradation):

    name = "mix"
    description = ("Mix input with a specified noise. " +
                   "The noise can be specified with its full path or "
                   "relative to the resources directory (see -l option)")
    parameters_info = [("noise",
                        "sounds/ambience-pub.wav",
                        "Full or relative path (to resources dir) of noise"),
                       ("snr",
                        "6",
                        "Desired Signal-to-Noise-Ratio [dB]")]

    def read_noise(self, noise_path, degraded_audio_file):
        """ Read samples of noise resampled at the sample_rate of input

        Args:
            degraded_audio_file (DegradedAudioFile): Input DegradedAudioFile
        Returns:
            (np.array): Samples of noise with shape (2, nsamples)
        """
        sample_rate = degraded_audio_file.sample_rate
        aux_x_noise, _ = lr.core.load(noise_path, sr=sample_rate, mono=False)
        if len(aux_x_noise.shape) == 1:
            noise_samples = np.zeros((2, len(aux_x_noise)))
            noise_samples[0, :] = aux_x_noise
            noise_samples[1, :] = aux_x_noise
        else:
            noise_samples = aux_x_noise
        return noise_samples

    def adjust_noise_duration(self, noise_samples, degraded_audio_file):
        """ Adjust the duration of noise_samples to fit degraded_audio_file

        In case it is shorter, it repeats the noise.

        Args:
            noise_samples (np.array): Samples of noise with shape (2, nsamples)
            degraded_audio_file (DegradedAudioFile): Input audio
        Returns:
            (np.array): Samples of noise with shape (2, new_nsamples)
        """
        input_num_samples = degraded_audio_file.samples.shape[1]
        while noise_samples.shape[1] < input_num_samples:
            noise_samples = np.concatenate((noise_samples, noise_samples),
                                           axis=1)
        noise_samples = noise_samples[:, :input_num_samples]
        return noise_samples

    def get_actual_noise_path(self):
        """ Resolve full path of noise

        The specified noise path could be a relative path
        """
        import audio_degrader
        resources_dir = os.path.join(audio_degrader.__path__[0],
                                     'resources')
        noise_path = self.parameters_values['noise']
        if not os.path.isfile(noise_path):
            noise_path = os.path.join(resources_dir, noise_path)
        return noise_path

    def get_noise_gain_factor(self, snr_dbs, rms_noise, rms_input):
        """ Get gain factor that should be applied to noise

        Args:
            snr_dbs (float): Desired SNR in dBs
            rms_noise (float): RMS value of noise
            rms_input (float): RMS value of input
        Returns:
            (float): Noise gain factor
        """
        logging.debug("RMS noise: %f" % rms_noise)
        logging.debug("RMS input: %f" % rms_input)
        snr_linear = 10 ** (snr_dbs / 20.0)
        logging.debug("SNR , SNR linear: %f , %f" % (snr_dbs, snr_linear))
        noise_gain_factor = rms_input / rms_noise / snr_linear
        logging.debug("noise_gain_factor: %f" % noise_gain_factor)
        return noise_gain_factor

    def apply(self, degraded_audio_file):
        noise_path = self.get_actual_noise_path()
        noise_samples = self.adjust_noise_duration(
            self.read_noise(noise_path, degraded_audio_file),
            degraded_audio_file)
        rms_noise = np.sqrt(np.mean(np.power(noise_samples, 2)))
        rms_input = np.sqrt(np.mean(np.power(degraded_audio_file.samples, 2)))
        noise_gain_factor = self.get_noise_gain_factor(
            float(self.parameters_values['snr']),
            rms_noise,
            rms_input)
        y = degraded_audio_file.samples + noise_samples * noise_gain_factor
        # Normalize output RMS to fit input RMS
        rms_y = np.sqrt(np.mean(np.power(y, 2)))
        y = y * rms_input / rms_y
        degraded_audio_file.samples = y
