// The Python renderer's clipping, Bresenham stepping and depth rules, in C++.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>
#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C"
#endif
struct Point { double v[4]; };

static uint64_t line(uint8_t* pixels, double* depth, int w, int h,
                     Point a, Point b, const uint8_t* color) {
    for (int i=0;i<4;++i)
        if (!std::isfinite(a.v[i]) || !std::isfinite(b.v[i])) return 0;
    double da[7], db[7];
    for (int i=0;i<3;++i) {
        da[2*i]=a.v[3]+a.v[i]; da[2*i+1]=a.v[3]-a.v[i];
        db[2*i]=b.v[3]+b.v[i]; db[2*i+1]=b.v[3]-b.v[i];
    }
    da[6]=a.v[3]-1e-8; db[6]=b.v[3]-1e-8;
    double lo=0, hi=1;
    for (int i=0;i<7;++i) {
        if (da[i]<0 && db[i]<0) return 0;
        if (da[i]<0) lo=std::max(lo,da[i]/(da[i]-db[i]));
        else if (db[i]<0) hi=std::min(hi,da[i]/(da[i]-db[i]));
        if (lo>hi) return 0;
    }
    // Match clip_line's interpolation, including its all-inside fast path.
    bool inside=true;
    for (int i=0;i<7;++i) inside=inside && da[i]>=0 && db[i]>=0;
    if (!inside) {
        Point start=a;
        for (int i=0;i<4;++i) {
            a.v[i]=start.v[i]+(b.v[i]-start.v[i])*lo;
            b.v[i]=start.v[i]+(b.v[i]-start.v[i])*hi;
        }
    }
    // nearbyint uses ties-to-even, matching Python round (no fast-math).
    int x0=int(std::nearbyint((a.v[0]/a.v[3]*.5+.5)*(w-1)));
    int y0=int(std::nearbyint((.5-a.v[1]/a.v[3]*.5)*(h-1)));
    int x1=int(std::nearbyint((b.v[0]/b.v[3]*.5+.5)*(w-1)));
    int y1=int(std::nearbyint((.5-b.v[1]/b.v[3]*.5)*(h-1)));
    double z0=a.v[2]/a.v[3], z1=b.v[2]/b.v[3];
    int dx=std::abs(x1-x0), dy=-std::abs(y1-y0);
    int sx=x0<x1?1:-1, sy=y0<y1?1:-1, error=dx+dy;
    int steps=std::max(dx,-dy), i=0;
    uint64_t writes=0;
    while (true) {
        double z=z0+(z1-z0)*(steps?double(i)/steps:0.);
        if (x0>=0 && x0<w && y0>=0 && y0<h && z>=-1.000001 && z<=1.000001) {
            size_t index=size_t(y0)*w+x0;
            if (z<=depth[index]) {
                depth[index]=z;
                for (int c=0;c<3;++c) pixels[index*3+c]=color[c];
                ++writes;
            }
        }
        if (x0==x1 && y0==y1) break;
        int twice=2*error;
        if (twice>=dy) {error+=dy; x0+=sx;}
        if (twice<=dx) {error+=dx; y0+=sy;}
        ++i;
    }
    return writes;
}
API void clear_frame(uint8_t* pixels, double* depth, int w, int h, const uint8_t* color) {
    for (size_t i=0;i<size_t(w)*h;++i) {
        depth[i]=std::numeric_limits<double>::infinity();
        for (int c=0;c<3;++c) pixels[i*3+c]=color[c];
    }
}
API uint64_t draw_line(uint8_t* pixels, double* depth, int w, int h,
                       const double* endpoints, const uint8_t* color) {
    Point a,b;
    std::copy(endpoints,endpoints+4,a.v); std::copy(endpoints+4,endpoints+8,b.v);
    return line(pixels,depth,w,h,a,b,color);
}
API uint64_t draw_mesh(uint8_t* pixels, double* depth, int w, int h,
    const double* xyz, uint32_t count, const uint32_t* edges, uint32_t edge_count,
    const double* m, const uint8_t* color, int points) {
    try {
        std::vector<Point> clip(count);
        for (uint32_t i=0;i<count;++i) {
            double x=xyz[3*i], y=xyz[3*i+1], z=xyz[3*i+2];
            for (int j=0;j<4;++j) clip[i].v[j]=m[j]*x+m[4+j]*y+m[8+j]*z+m[12+j];
        }
        uint64_t writes=0;
        if (points) {
            for (const auto& p:clip) writes+=line(pixels,depth,w,h,p,p,color);
        } else {
            for (uint32_t i=0;i<edge_count;++i) {
                auto a=edges[2*i], b=edges[2*i+1];
                if (a<count && b<count) writes+=line(pixels,depth,w,h,clip[a],clip[b],color);
            }
        }
        return writes;
    } catch (...) { return UINT64_MAX; }
}
