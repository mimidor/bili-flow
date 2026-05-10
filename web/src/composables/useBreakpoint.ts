import { computed, onMounted, onBeforeUnmount, ref, type ComputedRef, type Ref } from "vue";

type BreakpointState = {
  width: Ref<number>;
  isMobile: ComputedRef<boolean>;
  isTablet: ComputedRef<boolean>;
  isDesktop: ComputedRef<boolean>;
};

export function useBreakpoint(mobileMax = 768, tabletMax = 1024): BreakpointState {
  const width = ref<number>(typeof window === "undefined" ? tabletMax : window.innerWidth);

  const updateWidth = () => {
    width.value = window.innerWidth;
  };

  onMounted(() => {
    updateWidth();
    window.addEventListener("resize", updateWidth, { passive: true });
  });

  onBeforeUnmount(() => {
    window.removeEventListener("resize", updateWidth);
  });

  const isMobile = computed(() => width.value <= mobileMax);
  const isTablet = computed(() => width.value > mobileMax && width.value <= tabletMax);
  const isDesktop = computed(() => width.value > tabletMax);

  return {
    width,
    isMobile,
    isTablet,
    isDesktop,
  };
}
