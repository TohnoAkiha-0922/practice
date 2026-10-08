#include "HalconCpp.h"

using namespace HalconCpp;

int main()
{
    // Create a 512x512 grayscale image with a circle pattern
    HImage img;
    img.GenImageConst("byte", 512, 512);

    // Generate a simple circle on the image
    HRegion circle;
    circle.GenCircle(256.0, 256.0, 150.0);
    HImage circleImg = circle.RegionToBin(255, 0, 512, 512);

    // Apply Sobel edge detection
    HImage edges = circleImg.SobelAmp("sum_abs", 3);

    // Threshold the edges
    HRegion edgeRegion = edges.Threshold(30, 255);

    // Save results
    circleImg.WriteImage("png", 0, "D:/code.c/Project20/circle_input.png");
    edges.WriteImage("png", 0, "D:/code.c/Project20/circle_edges.png");
    edgeRegion.RegionToBin(255, 0, 512, 512).WriteImage("png", 0, "D:/code.c/Project20/circle_threshold.png");

    // Print success
    printf("Halcon test completed! Output images saved.\n");
    return 0;
}
