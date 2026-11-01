// Máscara da pessoa (Vision, nativo do macOS): mascara <pasta_quadros> <pasta_saida>
// Lê cada .jpg/.png da pasta e grava um .png em tons de cinza (branco = pessoa).
#import <Foundation/Foundation.h>
#import <Vision/Vision.h>
#import <CoreImage/CoreImage.h>
#import <ImageIO/ImageIO.h>

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc != 3) { printf("uso: mascara <entrada> <saida>\n"); return 1; }
        NSString *ent = @(argv[1]), *sai = @(argv[2]);
        NSFileManager *fm = NSFileManager.defaultManager;
        [fm createDirectoryAtPath:sai withIntermediateDirectories:YES attributes:nil error:nil];
        NSArray *nomes = [[[fm contentsOfDirectoryAtPath:ent error:nil]
            filteredArrayUsingPredicate:[NSPredicate predicateWithFormat:@"self ENDSWITH '.jpg' OR self ENDSWITH '.png'"]]
            sortedArrayUsingSelector:@selector(compare:)];
        CIContext *ctx = [CIContext context];
        VNGeneratePersonSegmentationRequest *req = [VNGeneratePersonSegmentationRequest new];
        req.qualityLevel = VNGeneratePersonSegmentationRequestQualityLevelAccurate;
        req.outputPixelFormat = kCVPixelFormatType_OneComponent8;
        NSUInteger i = 0;
        for (NSString *n in nomes) {
            @autoreleasepool {
                NSURL *u = [NSURL fileURLWithPath:[ent stringByAppendingPathComponent:n]];
                CGImageSourceRef src = CGImageSourceCreateWithURL((__bridge CFURLRef)u, NULL);
                if (!src) continue;
                CGImageRef img = CGImageSourceCreateImageAtIndex(src, 0, NULL);
                CFRelease(src);
                VNImageRequestHandler *h = [[VNImageRequestHandler alloc] initWithCGImage:img options:@{}];
                NSError *err = nil;
                [h performRequests:@[req] error:&err];
                CGImageRelease(img);
                CVPixelBufferRef pb = req.results.firstObject.pixelBuffer;
                if (!pb) continue;
                CIImage *ci = [CIImage imageWithCVPixelBuffer:pb];
                CGImageRef cg = [ctx createCGImage:ci fromRect:ci.extent];
                NSString *saida = [sai stringByAppendingPathComponent:[[n stringByDeletingPathExtension] stringByAppendingString:@".png"]];
                CGImageDestinationRef dst = CGImageDestinationCreateWithURL((__bridge CFURLRef)[NSURL fileURLWithPath:saida],
                                                                            CFSTR("public.png"), 1, NULL);
                CGImageDestinationAddImage(dst, cg, NULL);
                CGImageDestinationFinalize(dst);
                CFRelease(dst); CGImageRelease(cg);
                if (i % 300 == 0) printf("%lu/%lu\n", (unsigned long)i, (unsigned long)nomes.count);
                i++;
            }
        }
        printf("ok %lu\n", (unsigned long)i);
    }
    return 0;
}
