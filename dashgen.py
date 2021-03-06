import argparse
import json

import os
import subprocess

encode_quality_command = \
    "docker run --rm -v {current_dir}:/media -u $(id -u):$(id -g) jrottenberg/ffmpeg:3.2 " \
    "-y -i /media/{video_file_name} " \
    "-c:v {codec} -crf {crf} -b:v 0 " \
    "-g {gop_size} -keyint_min {gop_size} -sc_threshold 0 " \
    "/media/{video_base_name}_{codec}_crf{crf}.{extension}"

encoded_quality_file = "{video_base_name}_{codec}_crf{crf}.{extension}"

encode_bitrate_command = \
    "docker run --rm -v {current_dir}:/media -u $(id -u):$(id -g) jrottenberg/ffmpeg:3.2 " \
    "-y -i /media/{video_file_name} " \
    "-c:v {codec} -b:v {bitrate} -maxrate {bitrate} -bufsize {bitrate} " \
    "-g {gop_size} -keyint_min {gop_size} -sc_threshold 0 " \
    "/media/{video_base_name}_{codec}_b{bitrate}.{extension}"

encoded_bitrate_file = "{video_base_name}_{codec}_b{bitrate}.{extension}"

ffprobe_duration = "docker run --rm --entrypoint='ffprobe' -v {current_dir}:/media -u $(id -u):$(id -g) jrottenberg/ffmpeg:3.2 " \
                   "-v quiet -print_format json -show_format -show_streams /media/{video_file_name}"

encode_quality_segment_command = \
    "docker run --rm -v {current_dir}:/media -u $(id -u):$(id -g) jrottenberg/ffmpeg:3.2 " \
    "-y -i /media/{video_file_name} " \
    "-ss {start_time} -t {duration} " \
    "-c:v {codec} -crf {crf} -b:v 0 " \
    "-g {gop_size} -keyint_min {gop_size} -sc_threshold 0 " \
    "/media/{video_base_name}_{codec}_crf{crf}_{start_time_format}.{extension}"

encode_quality_segment_from_yuv_segment_command = \
    "docker run --rm -v {current_dir}:/media -u $(id -u):$(id -g) jrottenberg/ffmpeg:3.2 " \
    "-s {width}x{height} " \
    "-y -i /media/{video_file_name} " \
    "-c:v {codec} -crf {crf} -b:v 0 " \
    "-g {gop_size} -keyint_min {gop_size} -sc_threshold 0 " \
    "/media/{video_base_name}_{codec}_crf{crf}_{start_time_format}.{extension}"

decode_quality_segment_command = \
    "docker run --rm -v {current_dir}:/media -u $(id -u):$(id -g) jrottenberg/ffmpeg:3.2 " \
    "-y -i /media/{video_file_name} " \
    "/media/{video_base_name}_{codec}_crf{crf}_{start_time_format}.{extension}"

decode_bitrate_segment_command = \
    "docker run --rm -v {current_dir}:/media -u $(id -u):$(id -g) jrottenberg/ffmpeg:3.2 " \
    "-y -i /media/{video_file_name} " \
    "/media/{video_base_name}_{codec}_b{bitrate}_{start_time_format}.{extension}"

encode_bitrate_segment_command = \
    "docker run --rm -v {current_dir}:/media -u $(id -u):$(id -g) jrottenberg/ffmpeg:3.2 " \
    "-y -i /media/{video_file_name} " \
    "-ss {start_time} -t {duration} " \
    "-c:v {codec} -b:v {bitrate} -maxrate {bitrate} -bufsize {bitrate} " \
    "-g {gop_size} -keyint_min {gop_size} -sc_threshold 0 " \
    "/media/{video_base_name}_{codec}_b{bitrate}_{start_time_format}.{extension}"

encode_yuv_segment = \
    "docker run --rm -v {current_dir}:/media -u $(id -u):$(id -g) jrottenberg/ffmpeg:3.2 " \
    "-y -i /media/{video_file_name} " \
    "-ss {start_time} -t {duration} " \
    "/media/{video_base_name}_{start_time_format}.{extension}"

psnr_command = "docker run --rm -v {current_dir}:/media -u $(id -u):$(id -g) jrottenberg/ffmpeg:3.2 " \
               "-i /media/{file_orig} -i /media/{file_compare} -lavfi psnr " \
               "-f null - 2>&1 | grep average | cut -d' ' -f8 | cut -d':' -f2"
vmaf_command = "docker run --rm -i -v $(pwd):/files vmaf" \
               " run_vmaf yuv420p {width} {height} /files/{file_orig} /files/{file_compare} --out-fmt json"
psnr_quality_file = "{video_base_name}_{codec}_crf{crf}_{start_time_format}.{extension}"
psnr_bitrate_file = "{video_base_name}_{codec}_b{bitrate}_{start_time_format}.{extension}"
psnr_yuv_file = "{video_base_name}_{start_time_format}.{extension}"

parser = argparse.ArgumentParser(description='Generate DASH Video')
group = parser.add_mutually_exclusive_group()

parser.add_argument('video')
group.add_argument('-q', '--qualities', nargs='+', help='Encoding qualities(crf)', type=int)
group.add_argument('-b', '--bitrates', nargs='+', help='Encoding bitrates(as ffmpeg likes: 500kbps, 1M...)', type=str)
parser.add_argument('-c', '--codec', help='Coded (ffmpeg)', type=str, required=True)
parser.add_argument('-ss', '--segment-size', help='Segment size(s)', type=int, required=True)
parser.add_argument('-fps', '--frames-per-second', help='Frames per second', type=int, default=24)
parser.add_argument('-psnr', '--calculate-psnr', action='store_true', help='Calculate PSNR')
parser.add_argument('-vmaf', '--calculate-vmaf', action='store_true', help='Calculate VMAF')
parser.add_argument('--clean', action='store_true', help='Remove segment files')

args = parser.parse_args()

print("Video file: %s" % args.video)
print("Codec: %s" % args.codec)
print("Qualities: %s" % args.qualities)
print("Segment Size: %d" % args.segment_size)
print("Calculate PSNR: %r" % args.calculate_psnr)
print("Remove quality segment files: %r" % args.clean)

if not args.qualities and not args.bitrates:
    print("Qualities of bitrates must be provided! Check help (-h) for more info")
    exit(-1)

# get file name
print("-----")
input_file = args.video
input_file_path = os.path.dirname(os.path.abspath(input_file))
input_file_basename = os.path.basename(input_file)
input_file = os.path.join(input_file_path, input_file_basename)
input_file_extensionless_basename = os.path.splitext(os.path.basename(input_file))[0]
print("Input file path: %s" % input_file_path)
print("Base name: %s" % input_file_basename)
print("Extensionless file: %s" % input_file_extensionless_basename)

if args.codec == 'libx264' or args.codec == "libx265":
    file_extension = 'mp4'
elif args.codec == 'vp9' or args.codec == "libaom-av1":
    file_extension = 'webm'

# check file existence
input_file_exists = os.path.isfile(input_file)
print("Video file exists: %s" % input_file_exists)

# get duration
ffprobe_command_string = ffprobe_duration.format(current_dir=input_file_path, video_file_name=input_file_basename)
print("Duration command: %s" % ffprobe_command_string)
ffprobe_command_result = subprocess.check_output(ffprobe_command_string, shell=True)
ffprobe_command_json = json.loads(ffprobe_command_result.decode())
video_duration = int(float(ffprobe_command_json["streams"][0]["duration"]))
video_width = int(float(ffprobe_command_json["streams"][0]["coded_width"]))
video_height = int(float(ffprobe_command_json["streams"][0]["coded_height"]))
print("Video duration: %ds" % video_duration)
print("Video resolution: %dx%d" % (video_width, video_height))

psnrs = {}
vmafs = {}

if args.qualities:
    print("Encoding qualities....")
    for i in args.qualities:
        print("\n\n**CRF: %d" % i)

        # encoded file name
        encoded_file_name = encoded_quality_file.format(video_base_name=input_file_extensionless_basename,
                                                        codec=args.codec,
                                                        crf=i,
                                                        extension=file_extension)
        # check if it exists
        encoded_file_exists = os.path.isfile(encoded_file_name)
        print("Encoded file exists: %s" % encoded_file_exists)
        # if not, create it
        if not encoded_file_exists:
            encode_command_string = encode_quality_command.format(current_dir=input_file_path,
                                                                  video_file_name=input_file_basename,
                                                                  codec=args.codec,
                                                                  crf=i,
                                                                  gop_size=args.segment_size * args.frames_per_second,
                                                                  video_base_name=input_file_extensionless_basename,
                                                                  extension=file_extension)

            encode_result = subprocess.check_output(encode_command_string, shell=True)
        else:
            print("Escaping encoding file: %s" % encoded_file_name)

        # calculate segment vmaf
        vmaf_crf_list = []
        if args.calculate_vmaf:

            print("Pre-creating segment YUVs")
            for j in range(0, video_duration, args.segment_size):
                # yuv segment name
                file_segment_yuv = psnr_yuv_file.format(video_base_name=input_file_extensionless_basename,
                                                        start_time_format=str(j).zfill(3),
                                                        extension="yuv")
                # check if it exists
                segment_yuv_exists = os.path.isfile(file_segment_yuv)
                if not segment_yuv_exists:
                    print("Pre-creating segment YUVs: %d" % j)
                    encode_yuv_segment_string = encode_yuv_segment.format(current_dir=input_file_path,
                                                                          video_file_name=input_file_basename,
                                                                          start_time=j,
                                                                          start_time_format=str(j).zfill(3),
                                                                          duration=args.segment_size,
                                                                          video_base_name=input_file_extensionless_basename,
                                                                          extension="yuv")
                    print("Running: %s" % encode_yuv_segment_string)
                    encode_yuv_segment_result = subprocess.check_output(encode_yuv_segment_string, shell=True)
                else:
                    print("Escape creating yuv segment: %s" % file_segment_yuv)

            print("Computing VMAF")
            for j in range(0, video_duration, args.segment_size):
                print("\n*Segment: %d" % j)

                # source yuv file
                file_segment_yuv = psnr_yuv_file.format(video_base_name=input_file_extensionless_basename,
                                                        start_time_format=str(j).zfill(3),
                                                        extension="yuv")

                # encoded segment name
                file_segment_compare = psnr_quality_file.format(video_base_name=input_file_extensionless_basename,
                                                                codec=args.codec,
                                                                crf=i,
                                                                start_time_format=str(j).zfill(3),
                                                                extension=file_extension)

                file_segment_compare_yuv = psnr_quality_file.format(video_base_name=input_file_extensionless_basename,
                                                                codec=args.codec,
                                                                crf=i,
                                                                start_time_format=str(j).zfill(3),
                                                                extension="yuv")

                # check if it exists
                segment_encoded_exists = os.path.isfile(file_segment_compare)
                segment_encoded_yuv_exists = os.path.isfile(file_segment_compare_yuv)
                if not segment_encoded_exists:
                    # encode_command_segment_string = encode_quality_segment_command.format(current_dir=input_file_path,
                    #                                                                       video_file_name=input_file_basename,
                    #                                                                       start_time=j,
                    #                                                                       start_time_format=str(
                    #                                                                           j).zfill(3),
                    #                                                                       duration=args.segment_size,
                    #                                                                       codec=args.codec,
                    #                                                                       crf=i,
                    #                                                                       gop_size=args.segment_size * args.frames_per_second,
                    #                                                                       video_base_name=input_file_extensionless_basename,
                    #                                                                       extension=file_extension)
                    # print("Running: %s" % encode_command_segment_string)
                    # encode_segment_result = subprocess.check_output(encode_command_segment_string, shell=True)

                    encode_command_segment_string = encode_quality_segment_from_yuv_segment_command.format(current_dir=input_file_path,
                                                                                          video_file_name=file_segment_yuv,
                                                                                          start_time_format=str(
                                                                                              j).zfill(3),
                                                                                          width=video_width,
                                                                                          height=video_height,
                                                                                          codec=args.codec,
                                                                                          crf=i,
                                                                                          gop_size=args.segment_size * args.frames_per_second,
                                                                                          video_base_name=input_file_extensionless_basename,
                                                                                          extension=file_extension)
                    print("Running: %s" % encode_command_segment_string)
                    encode_segment_result = subprocess.check_output(encode_command_segment_string, shell=True)

                else:
                    print("Escape encoding segment: %s" % file_segment_compare)

                if not segment_encoded_yuv_exists:
                    decode_command_segment_string = decode_quality_segment_command.format(current_dir=input_file_path,
                                                                                          video_file_name=file_segment_compare,
                                                                                          start_time=j,
                                                                                          start_time_format=str(
                                                                                              j).zfill(3),
                                                                                          duration=args.segment_size,
                                                                                          codec=args.codec,
                                                                                          crf=i,
                                                                                          gop_size=args.segment_size * args.frames_per_second,
                                                                                          video_base_name=input_file_extensionless_basename,
                                                                                          extension="yuv")
                    print("Running: %s" % decode_command_segment_string)
                    decode_segment_result = subprocess.check_output(decode_command_segment_string, shell=True)

                else:
                    print("Escape encoding segment: %s" % file_segment_compare_yuv)

                # yuv segment name
                file_segment_yuv = psnr_yuv_file.format(video_base_name=input_file_extensionless_basename,
                                                        start_time_format=str(j).zfill(3),
                                                        extension="yuv")
                # check if it exists
                segment_yuv_exists = os.path.isfile(file_segment_yuv)
                if not segment_yuv_exists:
                    encode_yuv_segment_string = encode_yuv_segment.format(current_dir=input_file_path,
                                                                          video_file_name=input_file_basename,
                                                                          start_time=j,
                                                                          start_time_format=str(j).zfill(3),
                                                                          duration=args.segment_size,
                                                                          video_base_name=input_file_extensionless_basename,
                                                                          extension="yuv")
                    print("Running: %s" % encode_yuv_segment_string)
                    encode_yuv_segment_result = subprocess.check_output(encode_yuv_segment_string, shell=True)
                else:
                    print("Escape creating yuv segment: %s" % file_segment_yuv)

                # psnr
                print("Calculating VMAF for crf: %d, segment: %d" % (i, j))
                vmaf_command_string = vmaf_command.format(width=video_width,
                                                          height=video_height,
                                                          file_orig=file_segment_yuv,
                                                          file_compare=file_segment_compare_yuv)
                print("VMAF command: %s" % vmaf_command_string)
                vmaf_command_result = subprocess.check_output(vmaf_command_string, shell=True).decode().replace('\\n', '\n')
                vmaf_command_result_json = json.loads(vmaf_command_result)
                print("VMAF result: %s" % vmaf_command_result)
                vmaf_command_final = vmaf_command_result_json["aggregate"]["VMAF_score"]
                print("VMAF mean: %s" % vmaf_command_final)
                vmaf_crf_list.append(float(vmaf_command_final))
                if args.clean:
                    os.remove(file_segment_compare_yuv)
                    os.remove(file_segment_compare)
                    os.remove(file_segment_yuv)

            vmafs[i] = vmaf_crf_list
            print("\nVMAFs: %s" % vmafs)
            if args.qualities:
                psnr_file_diff = "_crf_vmaf"
            else:
                psnr_file_diff = "_bitrate_vmaf"
            with open(input_file_extensionless_basename + psnr_file_diff + ".json", 'w') as file:
                file.write(json.dumps(vmafs, sort_keys=False, indent=4, separators=(',', ': ')))

        # calculate segment psnr
        psnr_crf_list = []
        if args.calculate_psnr:
            for j in range(0, video_duration, args.segment_size):
                print("\n*Segment: %d" % j)

                # encoded segment name
                file_segment_compare = psnr_quality_file.format(video_base_name=input_file_extensionless_basename,
                                                                codec=args.codec,
                                                                crf=i,
                                                                start_time_format=str(j).zfill(3),
                                                                extension=file_extension)
                # check if it exists
                segment_encoded_exists = os.path.isfile(file_segment_compare)
                if not segment_encoded_exists:
                    encode_command_segment_string = encode_quality_segment_command.format(current_dir=input_file_path,
                                                                                          video_file_name=input_file_basename,
                                                                                          start_time=j,
                                                                                          start_time_format=str(j).zfill(3),
                                                                                          duration=args.segment_size,
                                                                                          codec=args.codec,
                                                                                          crf=i,
                                                                                          gop_size=args.segment_size * args.frames_per_second,
                                                                                          video_base_name=input_file_extensionless_basename,
                                                                                          extension=file_extension)

                    print("Running: %s" % encode_command_segment_string)
                    encode_segment_result = subprocess.check_output(encode_command_segment_string, shell=True)
                else:
                    print("Escape encoding segment: %s" % file_segment_compare)

                # yuv segment name
                file_segment_yuv = psnr_yuv_file.format(video_base_name=input_file_extensionless_basename,
                                                        start_time_format=str(j).zfill(3),
                                                        extension="y4m")
                # check if it exists
                segment_yuv_exists = os.path.isfile(file_segment_yuv)
                if not segment_yuv_exists:
                    encode_yuv_segment_string = encode_yuv_segment.format(current_dir=input_file_path,
                                                                          video_file_name=input_file_basename,
                                                                          start_time=j,
                                                                          start_time_format=str(j).zfill(3),
                                                                          duration=args.segment_size,
                                                                          video_base_name=input_file_extensionless_basename,
                                                                          extension="y4m")
                    print("Running: %s" % encode_yuv_segment_string)
                    encode_yuv_segment_result = subprocess.check_output(encode_yuv_segment_string, shell=True)
                else:
                    print("Escape creating yuv segment: %s" % file_segment_yuv)

                # psnr
                print("Calculating PSNR for crf: %d, segment: %d" % (i, j))
                psnr_command_string = psnr_command.format(current_dir=input_file_path,
                                                          file_orig=file_segment_yuv,
                                                          file_compare=file_segment_compare)
                print("PSNR command: %s" % psnr_command_string)
                psnr_command_result = subprocess.check_output(psnr_command_string, shell=True)
                print("PSNR result: %s" % psnr_command_result.decode().rsplit())
                psnr_crf_list.append(float(psnr_command_result.decode()))
                if args.clean:
                    os.remove(file_segment_yuv)
                    os.remove(file_segment_compare)

            psnrs[i] = psnr_crf_list
            print("\nPSNRS: %s" % psnrs)
            if args.qualities:
                psnr_file_diff = "_crf_psnr"
            else:
                psnr_file_diff = "_bitrate_psnr"
            with open(input_file_extensionless_basename + psnr_file_diff + ".json", 'w') as file:
                file.write(json.dumps(psnrs, sort_keys=False, indent=4, separators=(',', ': ')))

elif args.bitrates:
    print("Encoding bitrates....")
    for i in args.bitrates:
        print("\n\n**Bitrate: %s" % i)

        # encoded file name
        encoded_file_name = encoded_bitrate_file.format(video_base_name=input_file_extensionless_basename,
                                                        codec=args.codec,
                                                        bitrate=i,
                                                        extension=file_extension)
        # check if it exists
        encoded_file_exists = os.path.isfile(encoded_file_name)
        print("Encoded file exists: %s" % encoded_file_exists)
        # if not, create it
        if not encoded_file_exists:
            encode_command_string = encode_bitrate_command.format(current_dir=input_file_path,
                                                                  video_file_name=input_file_basename,
                                                                  codec=args.codec,
                                                                  bitrate=i,
                                                                  gop_size=args.segment_size * args.frames_per_second,
                                                                  video_base_name=input_file_extensionless_basename,
                                                                  extension=file_extension)

            print("Running: %s" % encode_command_string)
            encode_result = subprocess.check_output(encode_command_string, shell=True)
        else:
            print("Escaping encoding file: %s" % encoded_file_name)

        # calculate segment vmaf
        vmaf_bitrate_list = []
        if args.calculate_vmaf:
            print("Computing VMAF")
            for j in range(0, video_duration, args.segment_size):
                print("\n*Segment: %d" % j)

                # encoded segment name
                file_segment_compare = psnr_bitrate_file.format(video_base_name=input_file_extensionless_basename,
                                                                codec=args.codec,
                                                                bitrate=i,
                                                                start_time_format=str(j).zfill(3),
                                                                extension=file_extension)
                print("Segment encoded name: %s" % file_segment_compare)

                file_segment_compare_yuv = psnr_bitrate_file.format(video_base_name=input_file_extensionless_basename,
                                                                codec=args.codec,
                                                                bitrate=i,
                                                                start_time_format=str(j).zfill(3),
                                                                extension="yuv")

                print("Segment YUV name: %s" % file_segment_compare)

                # check if it exists
                segment_encoded_exists = os.path.isfile(file_segment_compare)
                segment_encoded_yuv_exists = os.path.isfile(file_segment_compare_yuv)
                if not segment_encoded_exists:
                    encode_command_segment_string = encode_bitrate_segment_command.format(current_dir=input_file_path,
                                                                                          video_file_name=input_file_basename,
                                                                                          start_time=j,
                                                                                          start_time_format=str(
                                                                                              j).zfill(3),
                                                                                          duration=args.segment_size,
                                                                                          codec=args.codec,
                                                                                          bitrate=i,
                                                                                          gop_size=args.segment_size * args.frames_per_second,
                                                                                          video_base_name=input_file_extensionless_basename,
                                                                                          extension=file_extension)
                    print("Running: %s" % encode_command_segment_string)
                    encode_segment_result = subprocess.check_output(encode_command_segment_string, shell=True)
                else:
                    print("Escape encoding segment: %s" % file_segment_compare)

                if not segment_encoded_yuv_exists:
                    decode_command_segment_string = decode_bitrate_segment_command.format(current_dir=input_file_path,
                                                                                          video_file_name=file_segment_compare,
                                                                                          start_time=j,
                                                                                          start_time_format=str(
                                                                                              j).zfill(3),
                                                                                          duration=args.segment_size,
                                                                                          codec=args.codec,
                                                                                          bitrate=i,
                                                                                          gop_size=args.segment_size * args.frames_per_second,
                                                                                          video_base_name=input_file_extensionless_basename,
                                                                                          extension="yuv")
                    print("Running: %s" % decode_command_segment_string)
                    decode_segment_result = subprocess.check_output(decode_command_segment_string, shell=True)

                else:
                    print("Escape encoding segment: %s" % file_segment_compare_yuv)

                # yuv segment name
                file_segment_yuv = psnr_yuv_file.format(video_base_name=input_file_extensionless_basename,
                                                        start_time_format=str(j).zfill(3),
                                                        extension="yuv")
                # check if it exists
                segment_yuv_exists = os.path.isfile(file_segment_yuv)
                if not segment_yuv_exists:
                    encode_yuv_segment_string = encode_yuv_segment.format(current_dir=input_file_path,
                                                                          video_file_name=input_file_basename,
                                                                          start_time=j,
                                                                          start_time_format=str(j).zfill(3),
                                                                          duration=args.segment_size,
                                                                          video_base_name=input_file_extensionless_basename,
                                                                          extension="yuv")
                    print("Running: %s" % encode_yuv_segment_string)
                    encode_yuv_segment_result = subprocess.check_output(encode_yuv_segment_string, shell=True)
                else:
                    print("Escape creating yuv segment: %s" % file_segment_yuv)

                # psnr
                print("Calculating VMAF for bitrate: %s, segment: %d" % (i, j))
                vmaf_command_string = vmaf_command.format(width=video_width,
                                                          height=video_height,
                                                          file_orig=file_segment_yuv,
                                                          file_compare=file_segment_compare_yuv)
                print("VMAF command: %s" % vmaf_command_string)
                vmaf_command_result = subprocess.check_output(vmaf_command_string, shell=True).decode().replace('\\n', '\n')
                vmaf_command_result_json = json.loads(vmaf_command_result)
                print("VMAF result: %s" % vmaf_command_result)
                vmaf_command_final = vmaf_command_result_json["aggregate"]["VMAF_score"]
                print("VMAF mean: %s" % vmaf_command_final)
                vmaf_bitrate_list.append(float(vmaf_command_final))
                if args.clean:
                    os.remove(file_segment_compare_yuv)
                    os.remove(file_segment_compare)
                    os.remove(file_segment_yuv)

            vmafs[i] = vmaf_bitrate_list
            print("\nVMAFs: %s" % vmafs)
            if args.qualities:
                psnr_file_diff = "_crf_vmaf"
            else:
                psnr_file_diff = "_bitrate_vmaf"
            with open(input_file_extensionless_basename + psnr_file_diff + ".json", 'w') as file:
                file.write(json.dumps(vmafs, sort_keys=False, indent=4, separators=(',', ': ')))






        # calculate segment psnr
        psnr_crf_list = []
        if args.calculate_psnr:
            for j in range(0, video_duration, args.segment_size):
                print("\n*Segment: %d" % j)

                # encoded segment name
                file_segment_compare = psnr_bitrate_file.format(video_base_name=input_file_extensionless_basename,
                                                                codec=args.codec,
                                                                bitrate=i,
                                                                start_time_format=str(j).zfill(3),
                                                                extension=file_extension)
                # check if it exists
                segment_encoded_exists = os.path.isfile(file_segment_compare)
                if not segment_encoded_exists:
                    encode_command_segment_string = encode_bitrate_segment_command.format(current_dir=input_file_path,
                                                                                          video_file_name=input_file_basename,
                                                                                          start_time=j,
                                                                                          start_time_format=str(j).zfill(3),
                                                                                          duration=args.segment_size,
                                                                                          codec=args.codec,
                                                                                          bitrate=i,
                                                                                          gop_size=args.segment_size * args.frames_per_second,
                                                                                          video_base_name=input_file_extensionless_basename,
                                                                                          extension=file_extension)
                    print("Running: %s" % encode_command_segment_string)
                    encode_segment_result = subprocess.check_output(encode_command_segment_string, shell=True)
                else:
                    print("Escape encoding segment: %s" % file_segment_compare)

                # yuv segment name
                file_segment_yuv = psnr_yuv_file.format(video_base_name=input_file_extensionless_basename,
                                                        start_time_format=str(j).zfill(3),
                                                        extension="y4m")
                # check if it exists
                segment_yuv_exists = os.path.isfile(file_segment_yuv)
                if not segment_yuv_exists:
                    encode_yuv_segment_string = encode_yuv_segment.format(current_dir=input_file_path,
                                                                          video_file_name=input_file_basename,
                                                                          start_time=j,
                                                                          start_time_format=str(j).zfill(3),
                                                                          duration=args.segment_size,
                                                                          video_base_name=input_file_extensionless_basename,
                                                                          extension="y4m")
                    print("Running: %s" % encode_yuv_segment_string)
                    encode_yuv_segment_result = subprocess.check_output(encode_yuv_segment_string, shell=True)
                else:
                    print("Escape creating yuv segment: %s" % file_segment_yuv)

                # psnr
                print("Calculating PSNR for bitrate: %s, segment: %d" % (i, j))
                psnr_command_string = psnr_command.format(current_dir=input_file_path,
                                                          file_orig=file_segment_yuv,
                                                          file_compare=file_segment_compare)
                # print("PSNR command: %s" % psnr_command_string)
                psnr_command_result = subprocess.check_output(psnr_command_string, shell=True)
                print("PSNR result: %s" % psnr_command_result.decode().rsplit())
                psnr_crf_list.append(float(psnr_command_result.decode()))
                if args.clean:
                    os.remove(file_segment_yuv)
                    os.remove(file_segment_compare)

            psnrs[i] = psnr_crf_list

            print("\nPSNRS: %s" % psnrs)
            if args.qualities:
                psnr_file_diff = "_crf_psnr"
            else:
                psnr_file_diff = "_bitrate_psnr"
            with open(input_file_extensionless_basename + psnr_file_diff + ".json", 'w') as file:
                file.write(json.dumps(psnrs, sort_keys=False, indent=4, separators=(',', ': ')))
